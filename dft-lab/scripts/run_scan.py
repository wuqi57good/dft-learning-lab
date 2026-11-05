"""重建并验收真实DUT的v1/v2扫描流程；只依赖Python与Icarus。

输入v0真实JSON和原功能TB；输出生成网表、DRC、测试平台、VCD、日志与验证报告。
文件生成由模型/插链工具负责；此入口只组织进程与硬性断言。
⚠ PASS是本项目自定义标记，绝非商业工具报告。所有失败立即停止交付。
"""
from copy import deepcopy
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'dft_tools'))
from netlist_model import load
from drc import check
from scan_insert import emit_verilog


def lockup_wave(mapping, module):
    """从真实DUT两次仿真的VCD取相同窗口；不是重画一组预设理想波形。"""
    failure = (ROOT/'reports/scan/missing_lockup.log').read_text(encoding='utf-8')
    match = re.search(r'chain=(\d+) step=(\d+)', failure)
    chain, step = map(int, match.groups())
    lock = next(item for item in mapping['lockups'] if item['chain'] == chain)
    sink = mapping['chains'][chain]['cells'][lock['before_position']]
    times = [4+12*step+offset for offset in [0, 2, 3, 4, 5, 6, 8, 10, 12]]
    targets = {'source_clock': 'scan_v2_tb.scan_clk', 'destination_clock': 'scan_v2_tb.scan_clk_aux',
               'source_q': f'scan_v2_tb.dut.n{lock["source_q"]}',
               'held_q': f'scan_v2_tb.dut.n{lock["held_q"]}',
               'destination_q': f'scan_v2_tb.dut.n{sink["q"]}'}

    def samples(path):
        scope, symbols, transitions = [], {}, {key: [] for key in targets}
        time = 0
        header = True
        text = path.read_text(encoding='utf-8')
        # 本TB固定timescale1ns/1ps，Icarus VCD精度1ps；遇到其它单位要显式扩展解析。
        if not re.search(r'\$timescale\s+1ps\s+\$end', text):
            raise ValueError('VCD timescale改变，不能继续按1ps解析')
        for line in text.splitlines():
            fields = line.split()
            if header:
                if fields and fields[0] == '$scope':
                    scope.append(fields[2])
                elif fields and fields[0] == '$upscope':
                    scope.pop()
                elif fields and fields[0] == '$var':
                    name = '.'.join(scope+[fields[4]])
                    for key, target in targets.items():
                        if name == target:
                            symbols.setdefault(fields[3], []).append(key)
                elif line.startswith('$enddefinitions'):
                    header = False
                continue
            if line.startswith('#'):
                time = int(line[1:])/1000
            elif line and line[0] in '01xz':
                for key in symbols.get(line[1:], []):
                    transitions[key].append((time, line[0]))
        if {key for keys in symbols.values() for key in keys} != set(targets):
            raise ValueError('缺少lockup波形信号')
        return [{'ns': ns, 'signals': {key: next((v for t, v in reversed(values) if t <= ns), 'x')
                                      for key, values in transitions.items()}} for ns in times]

    report = {'source': 'Icarus full-DUT VCD; sampled after delta cycles', 'chain': chain, 'step': step,
              'scope': '同一293FF DUT，aux晚2ns的教学shift协议；不是物理STA时序余量',
              'lockup': lock, 'destination': sink['instance'], 'signals': targets,
              'with_lockup': samples(ROOT/'build/scan/v2.vcd'),
              'without_lockup': samples(ROOT/'build/scan/missing_lockup.vcd')}
    assert any(a['signals']['destination_q'] != b['signals']['destination_q']
               for a, b in zip(report['with_lockup'], report['without_lockup']))
    (ROOT/'reports/scan/lockup_wave.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def functional_tb(version, module):
    """重用v0完整40事务参考模型，仅换DUT绑定，绝不降低原功能验收要求。"""
    text = (ROOT/'tb/functional_tb.sv').read_text(encoding='utf-8')
    name = 'dft_functional_' + version + '_tb'
    text = text.replace('functional_tb', name)
    text = text.replace('dft_demo_top dut(.*);', f'dft_demo_top_{version} dut(.*);')
    extra = ('reg test_mode=0,test_rst_n=1,scan_clk=0,scan_en=0,test_te=0;\n'
             '    reg scan_clk_aux=0; reg [31:0] test_bypass_data=0;\n'
             f'    reg [{0 if version == "v1" else 3}:0] scan_in=0; wire [{0 if version == "v1" else 3}:0] scan_out;\n')
    text = text.replace('    reg sys_clk', '    ' + extra + '    reg sys_clk')
    def net(name):
        bits = module['netnames'][name]['bits']
        return 'dut.n' + str(bits[0]) if len(bits) == 1 else '{' + ','.join('dut.n'+str(b) for b in reversed(bits)) + '}'
    text = text.replace('dut.shadow_parity', net('shadow_parity')).replace('dut.events_seen', net('events_seen'))
    text = text.replace('build/v0/functional.vcd', f'build/scan/functional_{version}.vcd')
    text = text.replace('FUNCTIONAL_V0', 'FUNCTIONAL_' + version.upper())
    return name, text


def scan_tb(version, module, mapping):
    """生成按报告链顺序自检的TB；移位期模型独立于DUT，capture后逐位读回。"""
    name = 'scan_' + version + '_tb'
    count = mapping['chain_count']
    max_len = max(c['length'] for c in mapping['chains'])
    shadow_q = module['netnames']['shadow_parity']['bits'][0]
    memory_index = next(i for i, c in enumerate(module['cells'].values()) if c['type'] == 'packet_mem')
    memory_name = f'cell_{memory_index}'
    declarations, shift_update, before, after, snapshot = [], [], [], [], []
    for chain in mapping['chains']:
        i, length = chain['index'], chain['length']
        declarations.append(f'reg [{length-1}:0] expected_{i};')
        initial = ''.join(str(r['reset_value']) for r in reversed(chain['cells']))
        declarations.append(f'initial expected_{i} = {length}\'b{initial};')
        before.append(f'if(scan_out[{i}] !== expected_{i}[{length-1}]) $fatal(1,"SO mismatch chain={i} step=%0d", step);')
        shift_update.append(f'expected_{i} = {{expected_{i}[{length-2}:0],scan_in[{i}]}};')
        bus = '{' + ','.join('dut.n'+str(r['q']) for r in reversed(chain['cells'])) + '}'
        after.append(f'if({bus} !== expected_{i}) $fatal(1,"state mismatch chain={i} step=%0d", step);')
        snapshot.append(f'expected_{i} = {bus};')
    extra_ports = ',.scan_clk_aux(scan_clk_aux),.test_bypass_data(test_bypass_data)' if version == 'v2' else ''
    memory_seed = f'for(i=0;i<32;i=i+1) dut.{memory_name}.storage[i]=32\'hcafe0000+i;' if version == 'v2' else ''
    memory_check = f'for(i=0;i<32;i=i+1) if(dut.{memory_name}.storage[i] !== (32\'hcafe0000+i)) $fatal(1,"test corrupted memory addr=%0d",i);' if version == 'v2' else ''
    shadow_check = f'if(dut.n{shadow_q} !== 1\'b1) $fatal(1,"bypass did not capture known parity");' if version == 'v2' else ''
    return name, f'''// 自动生成自检TB：链映射来自真实插入结果，shift期有独立序列化参考模型。
// CLK先正后负，SO正沿前采样。aux晚2ns；N单元位于P单元之前。
// Capture后保存实际Q快照再移出，另用已知旁路奇偶值验证v2捕获不是空操作。
`timescale 1ns/1ps
module {name};
reg sys_clk=0,aux_clk=0,rst_n_ext=1,cfg_valid=0,cfg_write=0,data_valid=0;
reg [7:0] cfg_addr=0; reg [31:0] cfg_wdata=0,data_in=0;
wire [31:0] cfg_rdata,data_out; wire cfg_ready,data_ready,data_out_valid,irq; wire [15:0] slow_ticks;
reg test_mode=1,test_rst_n=0,scan_clk=0,scan_clk_aux=0,scan_en=1,test_te=1;
reg [31:0] test_bypass_data=1;
reg [{count-1}:0] scan_in=0; wire [{count-1}:0] scan_out;
reg [31:0] random_state=32'h1a2b3c4d;
integer step,i;
{chr(10).join(declarations)}
dft_demo_top_{version} dut(.sys_clk(sys_clk),.aux_clk(aux_clk),.rst_n_ext(rst_n_ext),
.cfg_valid(cfg_valid),.cfg_write(cfg_write),.cfg_addr(cfg_addr),.cfg_wdata(cfg_wdata),
.cfg_rdata(cfg_rdata),.cfg_ready(cfg_ready),.data_valid(data_valid),.data_in(data_in),
.data_ready(data_ready),.data_out_valid(data_out_valid),.data_out(data_out),.irq(irq),.slow_ticks(slow_ticks),
.test_mode(test_mode),.test_rst_n(test_rst_n),.scan_clk(scan_clk),.scan_en(scan_en),
.test_te(test_te),.scan_in(scan_in),.scan_out(scan_out){extra_ports});
task cycle;
begin
  #3 scan_clk=1; sys_clk=1;
  #2 scan_clk_aux=1; aux_clk=1;
  #3 scan_clk=0; sys_clk=0;
  #2 scan_clk_aux=0; aux_clk=0;
  #2;
end
endtask
task shift_once;
begin
  {chr(10).join(before)}
  {chr(10).join(shift_update)}
  cycle;
  {chr(10).join(after)}
end
endtask
initial begin
  $dumpfile("build/scan/{version}.vcd"); $dumpvars(0,{name});
  // 创建确定的复位事件；RTL reg初值不能替代一个真实reset脉冲。
  #1 test_rst_n=1; #1 test_rst_n=0; #2 test_rst_n=1;
  {memory_seed}
  for(step=0;step<{max_len*2};step=step+1) begin
    random_state={{random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]}};
    scan_in=random_state; shift_once;
  end
  $display("PASS SHIFT_{version.upper()} cells={mapping['scan_cell_count']} cycles={max_len*2}");
  // 扫入全零，避免功能enable/地址随机状态干扰可解释的capture实验。
  scan_in=0;
  for(step=0;step<{max_len};step=step+1) shift_once;
  scan_en=0; cycle;
  {shadow_check}
  {chr(10).join(snapshot)}
  scan_en=1;
  for(step=0;step<{max_len};step=step+1) shift_once;
  {memory_check}
  $display("PASS CAPTURE_AND_SHIFT_OUT_{version.upper()}");
  $display("PASS SCAN_{version.upper()}"); $finish;
end
initial begin #100000; $fatal(1,"scan watchdog"); end
endmodule
'''


def main():
    parser = argparse.ArgumentParser(description='实际DUT全链插入、DRC及正反例回归')
    parser.add_argument('--iverilog', default='iverilog')
    parser.add_argument('--vvp', default='vvp')
    args = parser.parse_args()
    # 单独重跑也立即使旧结果失效；缺工具或中断不能沿用上轮PASS。
    destination = ROOT/'reports/scan/validation.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({'status': 'RUNNING'}, indent=2), encoding='utf-8')
    iverilog, vvp = shutil.which(args.iverilog), shutil.which(args.vvp)
    if not iverilog or not vvp:
        raise SystemExit('需要iverilog/vvp；可通过--iverilog/--vvp指定可执行文件')
    env = os.environ.copy()
    # Windows Icarus的内部ivl也需要同目录DLL，因此绝对exe路径之外还设置子进程PATH。
    env['PATH'] = str(Path(iverilog).parent) + os.pathsep + env.get('PATH', '')
    env['PYTHONUTF8'] = '1'
    for directory in ['build/scan', 'reports/scan', 'reports/drc']:
        (ROOT/directory).mkdir(parents=True, exist_ok=True)

    def run(command, stem, expect_fail=False, token=None):
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        (ROOT/f'reports/scan/{stem}.log').write_text(result.stdout, encoding='utf-8')
        if expect_fail:
            if result.returncode == 0 or 'FATAL' not in result.stdout:
                raise RuntimeError(f'反例未被断言拦截: {stem}\n{result.stdout}')
        elif result.returncode or token and token not in result.stdout:
            raise RuntimeError(f'执行失败: {stem}\n{result.stdout}')
        print(stem, 'EXPECTED_FAIL' if expect_fail else 'PASS')
        return result.stdout

    for script in ['dft_report', 'scan_insert', 'drc']:
        run([sys.executable, f'dft_tools/{script}.py'], script)
    mapping = load(ROOT/'reports/scan_chains.json')
    common = ['rtl/v1/scan_dff.sv', 'rtl/v2/lockup_latch.sv', 'rtl/v0/packet_mem.sv']
    summary = {'schema': 'dft-lab.scan-validation.v1', 'status': 'PASS', 'versions': {}, 'negative_tests': []}
    for version in ['v1', 'v2']:
        module = next(iter(load(ROOT/f'netlist/{version}/design.json')['modules'].values()))
        version_report = {'scan_cells': mapping[version]['scan_cell_count'],
                          'chain_lengths': [c['length'] for c in mapping[version]['chains']],
                          'lockup_count': len(mapping[version]['lockups']),
                          'waveform': f'build/scan/{version}.vcd'}
        for kind, builder in [('functional', functional_tb), ('scan', scan_tb)]:
            name, text = builder(version, module) if kind == 'functional' else builder(version, module, mapping[version])
            (ROOT/f'tb/{name}.sv').write_text(text, encoding='utf-8')
            run([iverilog, '-g2012', '-s', name, '-o', f'build/scan/{name}.vvp',
                 f'netlist/{version}/design.v', *common, f'tb/{name}.sv'], name+'_compile')
            output = run([vvp, f'build/scan/{name}.vvp'], name, token=f'PASS {kind.upper()}_{version.upper()}')
            version_report[kind] = {'status': 'PASS', 'markers': [line for line in output.splitlines() if line.startswith('PASS')]}
        summary['versions'][version] = version_report
    # 反例改的是复制网表，交付网表永远保持正确版。每个故障先过DRC再跑HDL断言。
    module = next(iter(load(ROOT/'netlist/v2/design.json')['modules'].values()))
    mutations = {}
    broken_si = deepcopy(module)
    broken_si['cells'][mapping['v2']['chains'][0]['cells'][2]['instance']]['connections']['SI'] = ['0']
    mutations['broken_scan_link'] = broken_si
    missing_lockup = deepcopy(module)
    for lock in mapping['v2']['lockups']:
        entry = mapping['v2']['chains'][lock['chain']]['cells'][lock['before_position']]
        missing_lockup['cells'][entry['instance']]['connections']['SI'] = [lock['source_q']]
    mutations['missing_lockup'] = missing_lockup
    bad_memory = deepcopy(module)
    for cell in bad_memory['cells'].values():
        if cell['type'] == 'packet_mem':
            cell['connections']['we'] = ['1']
    mutations['memory_write_unguarded'] = bad_memory
    for label, bad in mutations.items():
        drc = check(bad, 'v2', mapping['v2'])
        if drc['pass']:
            raise AssertionError('DRC未拒绝故意错误: '+label)
        bad_file = f'build/scan/{label}.v'
        (ROOT/bad_file).write_text(emit_verilog(bad, 'dft_demo_top_v2'), encoding='utf-8')
        # 每个反例写独立VCD，禁止后跑的失败用例覆盖已经通过的正确波形证据。
        bad_tb = f'build/scan/{label}_tb.sv'
        tb_text = (ROOT/'tb/scan_v2_tb.sv').read_text(encoding='utf-8').replace(
            'build/scan/v2.vcd', f'build/scan/{label}.vcd')
        (ROOT/bad_tb).write_text(tb_text, encoding='utf-8')
        run([iverilog, '-g2012', '-s', 'scan_v2_tb', '-o', f'build/scan/{label}.vvp',
             bad_file, *common, bad_tb], label+'_compile')
        output = run([vvp, f'build/scan/{label}.vvp'], label, expect_fail=True)
        summary['negative_tests'].append({'name': label, 'drc_rejected': True, 'simulation_rejected': True,
                                          'waveform': f'build/scan/{label}.vcd',
                                          'failure': next(line for line in output.splitlines() if 'FATAL' in line)})
    lockup_wave(mapping['v2'], module)
    summary['lockup_waveform_report'] = 'reports/scan/lockup_wave.json'
    (ROOT/'reports/scan/validation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS SCAN_VALIDATION')


if __name__ == '__main__':
    main()
