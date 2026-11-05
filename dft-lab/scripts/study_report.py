"""用途：第二周把真实 VCD 和结构实验日志整理成网页可回放的证据。
输入：build/v0/functional.vcd、structures.vcd、reports/structures.log。
输出：reports/week2.json；字段全部由本项目定义，不冒充 EDA 厂商报告。
依赖：Python 标准库；先运行 run.py sim 与 run.py structures。
时序：只读取 Icarus 生成的 1ps VCD，在同一时刻所有事件结束后取快照。
边界：不进行 STA、不推断亚稳态、不把这些结构实验说成全 DUT 故障仿真。
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def sample_vcd(path, names, times_ns):
    """把完整层次名映射到 VCD id；向量保留 X/Z，绝不用零替换未知值。

    names: 需要展示的短标签到完整层次名；times_ns: 实际取样时刻列表。
    返回: 按时间排序的快照。每个值同时提供原始 bit 串与便于阅读的字符串。
    只接受本项目的 1ps 输出，单位不符就失败，避免错把 ps 数字当 ns。
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not re.search(r"\$timescale\s+1ps\s+\$end", "\n".join(lines)):
        raise ValueError("当前提取器只接受已确认的 1ps VCD")
    scope, signals, current, result = [], {}, {}, []
    wanted = sorted(times_ns)
    index, stamp = 0, 0

    def snapshot(ns):
        row = {}
        for label, full_name in names.items():
            wire, width = signals[full_name]
            bits = current.get(wire, "x").lower()
            # VCD 允许省略前导 0；x/z 的缩写必须用同类未知位扩展。
            bits = bits.rjust(width, bits[0] if bits[0] in "xz" else "0")
            value = bits.upper() if "x" in bits or "z" in bits else (
                "0x" + format(int(bits, 2), f"0{(width+3)//4}X") if width > 4 else str(int(bits, 2))
            )
            row[label] = {"bits": bits, "display": value}
        return {"ns": ns, "values": row}

    for line in lines:
        if line.startswith("$scope"):
            scope.append(line.split()[2])
        elif line.startswith("$upscope"):
            scope.pop()
        elif line.startswith("$var"):
            parts = line.split()
            signals[".".join(scope + [parts[4]])] = (parts[3], int(parts[2]))
        elif line.startswith("#"):
            stamp = int(line[1:])
            # 必须等下一时间戳到来才保存上一时刻；否则会漏掉 NBA 更新。
            while index < len(wanted) and wanted[index] * 1000 < stamp:
                result.append(snapshot(wanted[index]))
                index += 1
        elif line.startswith(("b", "B")):
            bits, wire = line[1:].split()
            current[wire] = bits
        elif line and line[0] in "01xz":
            current[line[1:]] = line[0]
    while index < len(wanted):
        if wanted[index] * 1000 > stamp:
            raise ValueError("请求的快照时间超出 VCD 实际结束时间")
        result.append(snapshot(wanted[index]))
        index += 1
    return result


def main():
    """解析日志、抽取波形并检查关键因果，全部通过才写出新报告。"""
    log = (ROOT / "reports/structures.log").read_text(encoding="utf-8")
    required = ["W2_ICG", "W2_MEMORY", "W2_CLOCK_RESET", "W2_FAULT_TRUTH", "W2_CDC", "STRUCTURES_V0"]
    for marker in required:
        if "PASS " + marker not in log:
            raise ValueError("结构实验未完成：" + marker)
    match = re.search(r"vectors=(\d+) r_sa0=(\d+) r_sa1=(\d+) q_sa1=(\d+)", log)
    if not match:
        raise ValueError("缺少穷举故障计数")
    counts = dict(zip(["vectors", "r_sa0", "r_sa1", "q_sa1"], map(int, match.groups())))

    # 路径来自实际层次声明，不通过变量名模糊匹配，避免选到其他实例的同名信号。
    transaction_names = {
        "valid": "functional_tb.data_valid", "ready": "functional_tb.data_ready",
        "data_in": "functional_tb.data_in", "word_q": "functional_tb.dut.word_q",
        "execute": "functional_tb.dut.execute", "commit": "functional_tb.dut.commit",
        "result": "functional_tb.data_out", "write_pointer": "functional_tb.dut.write_pointer",
        "mem_data": "functional_tb.dut.mem_data", "shadow": "functional_tb.dut.shadow_parity",
    }
    structure_names = {
        "clk": "structures_tb.clk", "enable": "structures_tb.gate_enable",
        "gated_clk": "structures_tb.gate.gated_clk", "direct_clk": "structures_tb.bad_clk",
        "good_count": "structures_tb.good_count", "bad_count": "structures_tb.bad_count",
        "mem_we": "structures_tb.mem_we", "mem_rdata": "structures_tb.mem_rdata",
        "shadow": "structures_tb.shadow", "soft_reset": "structures_tb.soft_reset",
        "core_rst_n": "structures_tb.core_rst_n", "slow_ticks": "structures_tb.slow_ticks",
        "status": "structures_tb.status", "neg_sample": "structures_tb.neg_sample",
        "source_events": "structures_tb.source_events", "target_events": "structures_tb.target_events",
    }
    transaction = sample_vcd(ROOT / "build/v0/functional.vcd", transaction_names, [80, 85, 90, 95, 100, 105, 115, 125])
    structure = sample_vcd(ROOT / "build/v0/structures.vcd", structure_names, [18, 26, 28, 36, 46, 56, 67, 71, 73, 81, 1000])
    by_time = {row["ns"]: row["values"] for row in structure}
    # 四态判断用 bit 串；单纯 int 转换会丢失 X，掩盖 memory 周边问题。
    assert "x" in by_time[36]["mem_rdata"]["bits"]
    assert by_time[46]["mem_rdata"]["display"] == "0x00000001"
    assert by_time[46]["shadow"]["bits"] == "x"
    assert by_time[56]["shadow"]["bits"] == "1"
    assert by_time[18]["good_count"]["display"] == "0x0000"
    assert by_time[18]["bad_count"]["display"] == "0x0001"
    assert by_time[28]["gated_clk"]["bits"] == "1" and by_time[28]["direct_clk"]["bits"] == "0"
    assert by_time[73]["core_rst_n"]["bits"] == "0"
    assert by_time[73]["neg_sample"]["bits"] == "0000"
    assert counts == {"vectors": 32, "r_sa0": 0, "r_sa1": 16, "q_sa1": 16}

    report = {
        "schema": "dft-lab.week2.v0", "status": "PASS", "timescale": "1ps",
        "fault_detection_input_counts": counts, "transaction": transaction, "structures": structure,
        "log": log, "limits": "RTL 四态示例实测；非完整 ATPG、非 STA、非 NAND2 等效面积。",
    }
    (ROOT / "reports/week2.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS WEEK2_EVIDENCE: 19 snapshots, X preserved, gate/reset/fault observations checked")


if __name__ == "__main__":
    main()

