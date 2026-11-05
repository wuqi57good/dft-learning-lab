"""将实际 VCD 中指定信号的变化转换为网页可审计的波形数据。

输入 Icarus Verilog VCD；输出 timescale、层级名和原始 bit 字符串。
不填补未知值、不发明边沿，不把脚本中的期望值当成仿真结果。v3 只处理
本项目使用的标量/向量 var、#time、bvalue 和标量变化；不读 real/string。
"""
from pathlib import Path


def read_vcd(path, suffixes=()):
    scopes, names, changes, time, header = [], {}, [], 0, True
    timescale = "unknown"
    lines = iter(Path(path).read_text(encoding="utf-8").splitlines())
    for raw in lines:
        line = raw.strip()
        if line.startswith("$timescale"):
            parts = [line.replace("$timescale", "").replace("$end", "").strip()]
            while "$end" not in line:
                line = next(lines).strip()
                parts.append(line.replace("$end", "").strip())
            timescale = " ".join(p for p in parts if p)
        elif line.startswith("$scope"):
            scopes.append(line.split()[2])
        elif line.startswith("$upscope"):
            scopes.pop()
        elif line.startswith("$var"):
            p = line.split()
            name = ".".join(scopes + [p[4]])
            if not suffixes or any(name.endswith(s) for s in suffixes):
                names.setdefault(p[3], []).append(name)
        elif line.startswith("$enddefinitions"):
            header = False
        elif not header and line.startswith("#"):
            time = int(line[1:])
        elif not header and line and not line.startswith("$"):
            if line[0] in "bB":
                bits, code = line[1:].split()
            elif line[0] in "01xXzZ":
                bits, code = line[0], line[1:]
            else:
                continue
            for name in names.get(code, []):
                changes.append({"time": time, "signal": name, "bits": bits.lower()})
    return {"file": str(path), "timescale": timescale, "changes": changes}
