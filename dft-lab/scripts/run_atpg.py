"""第 6 周可复现实验：JSON → D-cube ATPG → 独立故障仿真 → HDL 对照。

输入 netlist/v0/design.json；输出 reports/atpg、fault、coverage 与 patterns。
依赖 Python 标准库、Icarus Verilog；run_scan.py 已运行时可加 --scan-replay
验证全 DUT 的装载/捕获/移出。此文件只调度，不偷偷改 DUT 或期望覆盖率。
"""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dft_tools"))
from atpg import generate
from coverage import coverage_curve
from fault_sim import Circuit, all_vectors, detected, simulate, symbol
from wave_annotation import read_vcd


def write_json(path, value):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run(command, log):
    environment = os.environ.copy()
    environment["PATH"] = str(Path(command[0]).resolve().parent) + os.pathsep + environment.get("PATH", "")
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=environment)
    text = result.stdout + result.stderr
    (ROOT / log).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / log).write_text(text, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"工具退出 {result.returncode}；检查 {log}\n{text[-2000:]}")
    return text


def cut_hdl(circuit, iverilog, vvp):
    """把 JSON 的门连接导出为可注故障 Verilog，让 HDL 引擎独立算真值。

    故障编号逐一覆盖 PI stem 和全部门输出。不是用 Python 的检测值驱动
    HDL 输出：Verilog 的 AND/OR/NOT 运算与 Python 三值仿真是两个实现。
    """
    folder = ROOT / "build/atpg"
    folder.mkdir(parents=True, exist_ok=True)
    bits = sorted({b for b, _ in circuit.faults()})
    lines = ["module injected_cone(input [4:0] vector, input integer site, stuck, output [1:0] result);"]
    for bit in bits:
        lines.append(f"wire n{bit};")
    for index, (_, bit) in enumerate(circuit.inputs.items()):
        lines.append(f"assign n{bit} = site=={bit} ? stuck[0] : vector[{4-index}];")
    for gate in circuit.gates:
        ins, out = gate["inputs"], gate["output"]
        expr = f"~n{ins[0]}" if gate["kind"] == "$_NOT_" else f"n{ins[0]} {'&' if gate['kind']=='$_AND_' else '|'} n{ins[1]}"
        lines.append(f"assign n{out} = site=={out} ? stuck[0] : ({expr});")
    lines.append("assign result = {" + ",".join("n"+str(b) for b in circuit.outputs.values()) + "};\nendmodule")
    lines += ["module cut_tb;", "reg [4:0] vector; integer site,stuck,v,f; wire [1:0] good,bad;",
              "injected_cone g(vector,-1,0,good); injected_cone b(vector,site,stuck,bad);",
              "initial begin", "for(v=0;v<32;v=v+1) begin vector=v;"]
    for index, (bit, stuck) in enumerate(circuit.faults()):
        lines.append(f'site={bit}; stuck={stuck}; #1; $display("OBS %0d {index} %b %b",v,good,bad);')
    lines += ['end $display("PASS ATPG_CUT_HDL"); $finish; end endmodule']
    source = folder / "cut_check.v"
    source.write_text("\n".join(lines)+"\n", encoding="utf-8")
    run([iverilog, "-g2012", "-s", "cut_tb", "-o", "build/atpg/cut.vvp", "build/atpg/cut_check.v"], "reports/atpg/cut_compile.log")
    log = run([vvp, "build/atpg/cut.vvp"], "reports/atpg/cut_hdl.log")
    observed = [row.split() for row in log.splitlines() if row.startswith("OBS ")]
    vectors, faults = list(all_vectors(circuit)), circuit.faults()
    assert len(observed) == len(vectors)*len(faults)
    for _, v, f, good, bad in observed:
        vector, fault = vectors[int(v)], faults[int(f)]
        expected = ["".join(str(simulate(circuit, vector, inj)[b]) for b in circuit.outputs.values()) for inj in (None, fault)]
        assert [good, bad] == expected, (v, f, good, bad, expected)
    assert "PASS ATPG_CUT_HDL" in log
    return {"status": "PASS", "vectors": len(vectors), "faults": len(faults), "comparisons": len(observed)}


def scan_replay(circuit, results, iverilog, vvp):
    """把全部可测cut故障分别放进真实293FF DUT，验证装载、捕获和完整SO卸载。

    输入位按原cut端口及层次别名绑定，而非把所有故障硬指向q。原始stem
    对应的所有扇出共用一根实际网线，故障只在Capture窗口有效。目标响应
    用独立故障仿真确定；全链移出另外与Capture后快照逐位核对。
    """
    write_json('reports/atpg/scan_replay.json', {'status': 'RUNNING', 'cases': [],
               'scope': '完整DUT逐故障回放正在重建；不能沿用旧PASS'})
    mapping = json.loads((ROOT / "reports/scan_chains.json").read_text(encoding="utf-8"))["v2"]
    chains = mapping["chains"]
    max_length = max(c["length"] for c in chains)
    assert len(chains) == 4 and mapping["scan_cell_count"] == 293
    module = json.loads((ROOT / "netlist/v2/design.json").read_text(encoding="utf-8"))["modules"][mapping["top"]]
    original = json.loads((ROOT / "netlist/v0/design.json").read_text(encoding="utf-8"))["modules"]["fault_cone"]
    # local bit只在fault_cone模块内部有意义；必须借原始网名映射到展开后的bit。
    # 自动生成的~a节点没有友好名称，也从真实netnames追踪，不能漏掉net_10。
    fault_nets = {}
    for bit, _ in circuit.faults():
        matches = {module["netnames"]["u_fault."+name]["bits"][0]
                   for name, net in original["netnames"].items() if net["bits"] == [bit]}
        assert len(matches) == 1, (bit, matches)
        fault_nets[bit] = matches.pop()
    cells_by_alias = {}
    for chain in chains:
        for cell in chain["cells"]:
            for alias in cell["aliases"]:
                cells_by_alias[alias] = (chain["index"], cell["position"])
    input_positions = {name: cells_by_alias[f"u_ingress.word_q[{i}]"] for i, name in enumerate(circuit.inputs)}
    observations = {"reconv": "neg_status[1]", "redundant": "neg_status[2]"}
    detected_results = [item for item in results if item["status"] == "DETECTED"]
    cases = []
    demo_command = None
    for case in detected_results:
        bit, stuck = case["fault_bits"]
        values = [simulate(circuit, case["pattern"], inj) for inj in (None, (bit, stuck))]
        observable = [name for name, output in circuit.outputs.items()
                      if values[0][output] is not None and values[1][output] is not None
                      and values[0][output] != values[1][output]]
        assert observable, case["fault"]
        output_name = observable[0]
        obs_alias = observations[output_name]
        obs_chain, obs_position = cells_by_alias[obs_alias]
        obs_cycle = chains[obs_chain]["length"] - 1 - obs_position
        expected_good, expected_bad = [v[circuit.outputs[output_name]] for v in values]
        desired = [[0]*chain["length"] for chain in chains]
        for name, (chain, position) in input_positions.items():
            desired[chain][position] = case["pattern"][name]
        shifts = []
        for cycle in range(max_length):
            position = max_length - 1 - cycle
            values_in = [desired[c["index"]][position] if position < c["length"] else 0 for c in chains]
            shifts.append("".join(map(str, values_in[::-1])))
        slug = case["fault"].replace("/", "_")
        relative = "build/atpg" if case["fault"] == "q/SA1" else f"build/atpg/cases/{slug}"
        folder = ROOT / relative
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "scan_input.mem").write_text("\n".join(shifts)+"\n", encoding="ascii")
        corrupt_chain, corrupt_position = input_positions['a']
        header = ["// 自动取真实链与cut映射；参数用于一个故障的一次完整DUT回放。",
                  f"localparam SCAN_CYCLES={max_length}, OBS_CHAIN={obs_chain}, OBS_CYCLE={obs_cycle};",
                  f"localparam EXPECTED_GOOD=1'b{expected_good}, EXPECTED_BAD=1'b{expected_bad}, FAULT_VALUE=1'b{stuck};",
                  f"localparam INPUT_CORRUPT_CHAIN={corrupt_chain}, INPUT_CORRUPT_CYCLE={max_length-1-corrupt_position};",
                  f"`define FAULT_NET n{fault_nets[bit]}",
                  f'`define INPUT_FILE "{relative}/scan_input.mem"',
                  f'`define WAVE_FILE "{relative}/scan_atpg.vcd"',
                  "task check_loaded; begin"]
        for chain in chains:
            index, length = chain['index'], chain['length']
            expected = "".join(map(str, reversed(desired[index])))
            for dut in ['good', 'bad']:
                state = '{' + ','.join(f'{dut}.n{cell["q"]}' for cell in reversed(chain['cells'])) + '}'
                header.append(f'if ({state} !== {length}\'b{expected}) $fatal(1,"ATPG_LOAD_MISMATCH chain={index} dut={dut}");')
        header += ['end endtask', 'task snapshot_capture; begin']
        for chain in chains:
            for dut in ['good', 'bad']:
                state = '{' + ','.join(f'{dut}.n{cell["q"]}' for cell in reversed(chain['cells'])) + '}'
                header.append(f'captured_{dut}[{chain["index"]}] = {state};')
                header.append(f'if (^captured_{dut}[{chain["index"]}] === 1\'bx) '
                              f'$fatal(1,"ATPG_CAPTURE_X chain={chain["index"]} dut={dut}");')
        header += ['end endtask', 'task compare_shift; begin']
        for chain in chains:
            index, length = chain['index'], chain['length']
            for dut in ['good', 'bad']:
                header.append(f'if(cycle<{length} && {dut}_so[{index}] !== captured_{dut}[{index}][{length}-1-cycle]) '
                              f'$fatal(1,"ATPG_FULL_SHIFT_MISMATCH chain={index} dut={dut} cycle=%0d",cycle);')
        header += ['end endtask']
        task_start = header.index('task check_loaded; begin')
        (folder / "atpg_mapping.svh").write_text("\n".join(header[:task_start])+"\n", encoding="utf-8")
        # Icarus要求任务使用的数组先声明；参数先include，检查任务在DUT实例后include。
        (folder / "atpg_checks.svh").write_text("\n".join(header[task_start:])+"\n", encoding="utf-8")
        command = [iverilog, "-g2012", "-I", relative, "-s", "atpg_pattern_tb", "-o", relative+"/scan_atpg.vvp",
                   "rtl/v1/scan_dff.sv", "rtl/v2/lockup_latch.sv", "rtl/v0/packet_mem.sv",
                   "netlist/v2/design.v", "tb/atpg_pattern_tb.sv"]
        log_relative = "reports/atpg" if case["fault"] == "q/SA1" else f"reports/atpg/cases/{slug}"
        run(command, log_relative+"/scan_compile.log")
        log = run([vvp, relative+"/scan_atpg.vvp"], log_relative+"/scan_replay.log")
        assert all(marker in log for marker in ['PASS ATPG_SCAN_LOAD', 'PASS ATPG_SCAN_UNLOAD', 'PASS ATPG_FULL_DUT_SCAN'])
        observed = next(line for line in log.splitlines() if line.startswith('ATPG_SCAN_OBS '))
        assert f'good={expected_good} bad={expected_bad}' in observed
        cases.append({'fault': case['fault'], 'status': 'PASS', 'pattern': case['pattern'],
                      'fault_bit_in_cut': bit, 'fault_bit_in_dut': fault_nets[bit], 'stuck': stuck,
                      'observation': obs_alias, 'cut_output': output_name, 'observation_chain': obs_chain,
                      'observation_shift_cycle_zero_based': obs_cycle, 'good_bit': expected_good, 'bad_bit': expected_bad,
                      'loaded_cells_checked': mapping['scan_cell_count'], 'unloaded_cells_checked': mapping['scan_cell_count'],
                      'compared_so_bits': 2*mapping['scan_cell_count'], 'input_file': relative+'/scan_input.mem',
                      'vcd': relative+'/scan_atpg.vcd', 'log': log_relative+'/scan_replay.log'})
        if case['fault'] == 'q/SA1':
            demo_command = command
        print('PASS ATPG_FULL_DUT_CASE '+case['fault'])
    assert len(cases) == len(detected_results) and demo_command
    # 反例与成功案例共用同一验证断言；不同宏只破坏一处条件，日志和VCD完全隔离。
    negatives = []
    for macro, name, marker in [('OMIT_ATPG_FAULT', 'no_injection', 'ATPG_CAPTURE_OR_SHIFT_MISMATCH'),
                                 ('WRONG_ATPG_INPUT', 'wrong_input', 'ATPG_LOAD_MISMATCH'),
                                 ('WRONG_ATPG_OBSERVATION', 'wrong_observation', 'ATPG_CAPTURE_OR_SHIFT_MISMATCH')]:
        command = demo_command.copy()
        command[1:1] = ['-D'+macro]
        executable = 'build/atpg/negative_'+name+'.vvp'
        command[command.index('-o')+1] = executable
        run(command, 'reports/atpg/negative_'+name+'_compile.log')
        negative = subprocess.run([vvp, executable], cwd=ROOT, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace')
        text = negative.stdout+negative.stderr
        log_path = 'reports/atpg/negative_'+name+'.log'
        (ROOT/log_path).write_text(text, encoding='utf-8')
        assert negative.returncode != 0 and marker in text, (name, text)
        negatives.append({'name': name, 'status': 'EXPECTED_FAILURE', 'exit_code': negative.returncode,
                          'reason': marker, 'log': log_path, 'vcd': 'build/atpg/negative_'+name+'.vcd'})
    demo = next(case for case in cases if case['fault'] == 'q/SA1')
    wave = read_vcd(ROOT/demo['vcd'], ('scan_clk', 'scan_clk_aux', 'scan_en', 'scan_in', 'good_so', 'bad_so'))
    wave['file'] = demo['vcd']
    evidence = {**demo, 'top': mapping['top'], 'scan_cells': mapping['scan_cell_count'],
                'chains': [c['length'] for c in chains], 'waveform': wave,
                'negative_no_injection': negatives[0], 'negative_tests': negatives,
                'cases': cases, 'detected_replayed_count': len(cases),
                'total_compared_so_bits': sum(case['compared_so_bits'] for case in cases),
                'skipped_proven_untestable': [item['fault'] for item in results if item['status'] == 'PROVEN_UNTESTABLE_IN_CUT'],
                'scope': '当前组合cut全部19个可测故障逐例通过完整293FF DUT装载、捕获及SO卸载；不是全芯片故障覆盖率'}
    write_json('reports/atpg/scan_replay.json', evidence)
    print('PASS ATPG_FULL_DUT_SCAN cases='+str(len(cases)))


def main():
    parser = argparse.ArgumentParser(description="第六周 D-cube ATPG 与故障仿真")
    parser.add_argument("--iverilog", default="iverilog")
    parser.add_argument("--vvp", default="vvp")
    parser.add_argument("--scan-replay", action="store_true", help="在完整 v2 DUT 上扫描装载、捕获和移出")
    args = parser.parse_args()
    # 完整回放被单独重跑时，工具缺失或后续失败也不能保留旧PASS。
    if args.scan_replay:
        write_json('reports/atpg/scan_replay.json', {'status': 'RUNNING', 'cases': [],
                   'scope': '完整DUT逐故障回放已启动；不能沿用旧PASS'})
    iverilog, vvp = shutil.which(args.iverilog), shutil.which(args.vvp)
    if not iverilog or not vvp:
        parser.error("需要真实 Icarus Verilog；用 --iverilog/--vvp 指定路径")
    circuit = Circuit.load(ROOT / "netlist/v0/design.json")
    vectors, results, enhanced = list(all_vectors(circuit)), [], []
    observe_r = next(b for b, name in circuit.names.items() if name == "r")
    all_observe = list(circuit.outputs.values()) + [observe_r]
    for observation, observations, collection in [("primary_outputs", None, results), ("with_r_observe", all_observe, enhanced)]:
        for fault in circuit.faults():
            search = generate(circuit, fault, observations)
            witnesses = [v for v in vectors if detected(circuit, v, fault, observations)]
            assert bool(witnesses) == (search["pattern"] is not None), (circuit.label(fault), observation)
            if search["pattern"] is not None:
                assert detected(circuit, search["pattern"], fault, observations)
            collection.append({"fault": circuit.label(fault), "fault_bits": list(fault),
                               "status": "DETECTED" if witnesses else "PROVEN_UNTESTABLE_IN_CUT",
                               "pattern": search["pattern"], "detecting_vectors": len(witnesses),
                               "observation": observation, "trace": search["trace"]})
    q_demo = next(r for r in results if r["fault"] == "q/SA1")
    assert any(e["action"] == "conflict" for e in q_demo["trace"])
    assert any(e["action"] == "backtrack" for e in q_demo["trace"])
    good = simulate(circuit, q_demo["pattern"])
    bad = simulate(circuit, q_demo["pattern"], tuple(q_demo["fault_bits"]))
    q_demo["wave_symbols"] = {circuit.names[b]: symbol(good[b], bad[b]) for b in circuit.names}
    # 反例：激活故障并不保证传播。a=b=1 时 p=1，会屏蔽 q/SA1。
    masked = dict(a=1, b=1, c=0, d=0, e=0)
    assert good[q_demo["fault_bits"][0]] == 0
    assert not detected(circuit, masked, tuple(q_demo["fault_bits"]))
    # X 对照来自同一门模型；未知边界不能冒充已观察差异。
    x_vector = dict(a=None, b=1, c=0, d=0, e=0)
    p_fault = next(f for f in circuit.faults() if circuit.label(f) == "p/SA0")
    assert not detected(circuit, x_vector, p_fault)
    assert detected(circuit, {**x_vector, "a": 1}, p_fault)
    testable = sum(r["pattern"] is not None for r in results)
    summary = {"schema": "dft-lab.atpg.v3", "scope": "实际 DUT 的 fault_cone 组合 cut；不是全芯片覆盖率",
               "algorithm": "简化 D-cube 路径敏化与逆向 justification；非完整工业 D/J-frontier",
               "input_order": list(circuit.inputs), "gate_count": len(circuit.gates),
               "fault_model": "全部唯一 PI/门输出 stem 的 SA0/SA1，未折叠，不含 branch/延迟/scan cell 故障",
               "fault_count": len(results), "testable": testable, "oracle_vectors": len(vectors),
               "references": [
                   {"title": "Yosys JSON backend source", "url": "https://github.com/YosysHQ/yosys/blob/main/backends/json/json.cc", "checked": "2026-11-05"},
                   {"title": "NPTEL D-Algorithm: singular cover and D-frontier", "url": "https://archive.nptel.ac.in/content/storage2/courses/106103016/module9/lec2/1.html", "checked": "2026-11-05"},
                   {"title": "J. Paul Roth, Diagnosis of Automata Failures, 1966", "doi": "10.1147/rd.104.0278"}],
               "results": results, "trace_demo": q_demo,
               "uncovered": [r["fault"] for r in results if r["pattern"] is None],
               "x_boundary": {"unknown_vector": x_vector, "fault": circuit.label(p_fault),
                              "unknown_detected": False, "known_bypass_detected": True,
                              "scope": "同一 cut 的三值边界对照；非 memory 故障覆盖率"}}
    summary["hdl_crosscheck"] = cut_hdl(circuit, iverilog, vvp)
    points = coverage_curve(circuit, results+enhanced, [observe_r])
    coverage = {"schema": "dft-lab.coverage.v3", "scope": summary["scope"],
                "denominator": len(results), "testable": testable, "points": points,
                "fault_coverage": points[-1]["percent"],
                "test_coverage": 100*points[-1]["detected"]/testable,
                "observe_point": "新增观察 r 的组合模型对照；不把此值冒充已有 v2 输出端的覆盖率",
                "with_r_observe_testable": sum(r["pattern"] is not None for r in enhanced),
                "with_r_observe_final": points[-1]["with_observe"],
                "uncovered": summary["uncovered"], "random_seed": 20261105}
    assert points[-1]["detected"] == testable
    assert points[-1]["with_observe"] == sum(r["pattern"] is not None for r in enhanced)
    summary["negative_checks"] = {"activated_but_masked": "PASS", "unknown_not_counted_as_detected": "PASS",
                                  "oracle_agreement_all_faults": "PASS", "fixed_denominator": "PASS"}
    write_json("reports/atpg/summary.json", summary)
    write_json("reports/fault/fault_list.json", [{k: r[k] for k in ("fault", "fault_bits", "status", "detecting_vectors")} for r in results])
    write_json("reports/coverage/coverage.json", coverage)
    write_json("patterns/atpg/detection_patterns.json", {"input_order": list(circuit.inputs), "scope": summary["scope"],
                "patterns": [{k: r[k] for k in ("fault", "pattern")} for r in results if r["pattern"] is not None]})
    csv_out = io.StringIO()
    writer = csv.writer(csv_out)
    writer.writerow(["fault", *circuit.inputs, "status", "detecting_vectors"])
    for result in results:
        writer.writerow([result["fault"], *[(result["pattern"] or {}).get(n, "") for n in circuit.inputs], result["status"], result["detecting_vectors"]])
    (ROOT / "reports/fault/fault_results.csv").write_text(csv_out.getvalue(), encoding="utf-8")
    if args.scan_replay:
        scan_replay(circuit, results, iverilog, vvp)
    print(f"PASS ATPG_ORACLE faults={len(results)} testable={testable} vectors={len(vectors)}")
    print(f"PASS ATPG_CUT_HDL comparisons={summary['hdl_crosscheck']['comparisons']}")
    print(f"PASS COVERAGE_FIXED_DENOMINATOR {testable}/{len(results)}")


if __name__ == "__main__":
    main()
