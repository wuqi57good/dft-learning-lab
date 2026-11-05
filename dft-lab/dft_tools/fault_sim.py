"""从真实 Yosys JSON 读取组合 cut，执行独立的好/坏电路故障仿真。

输入是 design.json 中的 fault_cone，不是手写的期望真值表。输出保留逐线
的好/坏值；None 表示 X，X 绝不能算作已检测。v3 教学范围为单 bit 的
AND/OR/NOT 组合门及单一 stem stuck-at 故障，不处理 branch/桥接/延迟故障。
参考：Yosys write_json 的 ports/cells/connections/netnames 结构。
"""
from dataclasses import dataclass
from itertools import product
import json
from pathlib import Path


@dataclass
class Circuit:
    """门按拓扑顺序排列。相同 bit 的多个名字属于别名，不能重复计故障。"""
    inputs: dict
    outputs: dict
    gates: list
    names: dict

    @classmethod
    def load(cls, path, module="fault_cone"):
        mod = json.loads(Path(path).read_text(encoding="utf-8"))["modules"][module]
        inputs = {n: p["bits"][0] for n, p in mod["ports"].items() if p["direction"] == "input"}
        outputs = {n: p["bits"][0] for n, p in mod["ports"].items() if p["direction"] == "output"}
        if any(len(p["bits"]) != 1 for p in mod["ports"].values()):
            raise ValueError("本教学 cut 只支持单 bit 端口，拒绝静默截断宽总线")
        names = {b: n for n, p in mod["netnames"].items() if not p.get("hide_name") for b in p["bits"]}
        pending = []
        for name, cell in mod["cells"].items():
            kind = cell["type"]
            if kind not in ("$_AND_", "$_OR_", "$_NOT_"):
                raise ValueError(f"不支持的门 {name}: {kind}")
            c = cell["connections"]
            if any(len(bits) != 1 for bits in c.values()):
                raise ValueError("仅支持已映射的单 bit 通用门")
            ins = [c["A"][0]] + ([c["B"][0]] if "B" in c else [])
            out = c["Y"][0]
            names.setdefault(out, f"net_{out}")
            pending.append({"name": name, "kind": kind, "inputs": ins, "output": out})
        known, gates = set(inputs.values()) | {"0", "1"}, []
        while pending:
            ready = [g for g in pending if set(g["inputs"]) <= known]
            if not ready:
                raise ValueError("组合环或缺少驱动，不能伪造拓扑顺序")
            for gate in ready:
                gates.append(gate)
                known.add(gate["output"])
                pending.remove(gate)
        return cls(inputs, outputs, gates, names)

    def faults(self):
        """未折叠的逐线 stem 故障；分母来自网表唯一 bit，始终固定。"""
        bits = sorted(set(self.inputs.values()) | {g["output"] for g in self.gates})
        return [(bit, stuck) for bit in bits for stuck in (0, 1)]

    def label(self, fault):
        return f"{self.names[fault[0]]}/SA{fault[1]}"


def gate_value(kind, values):
    """三值逻辑的 controlling value 规则：0 AND X=0，1 OR X=1。"""
    if kind == "$_NOT_":
        return None if values[0] is None else 1 - values[0]
    if kind == "$_AND_":
        return 0 if 0 in values else None if None in values else 1
    if kind == "$_OR_":
        return 1 if 1 in values else None if None in values else 0
    raise ValueError(kind)


def simulate(circuit, vector, fault=None):
    """一次执行一个电路。故障在其 driver 输出立即覆盖，影响所有 fanout。

    vector 的 key 是 PI 名称；调用者必须明确提供每个 PI，避免把缺项当 0。
    None 可建模 memory 等未知边界，不能把它解释为 ATPG don't-care 已定值。
    """
    if set(vector) != set(circuit.inputs):
        raise ValueError("输入向量必须恰好包含全部 PI")
    if any(value not in (0, 1, None) for value in vector.values()):
        raise ValueError("仿真值只能为 0、1 或 None/X")
    values = {"0": 0, "1": 1}
    values.update({bit: vector[name] for name, bit in circuit.inputs.items()})
    if fault and fault[0] in values:
        values[fault[0]] = fault[1]
    for gate in circuit.gates:
        value = gate_value(gate["kind"], [values[b] for b in gate["inputs"]])
        values[gate["output"]] = fault[1] if fault and gate["output"] == fault[0] else value
    return values


def detected(circuit, vector, fault, observe=None):
    """只有好/坏两边都已知且不同才检测。额外观察点必须显式传入。"""
    good, bad = simulate(circuit, vector), simulate(circuit, vector, fault)
    return any(good[b] is not None and bad[b] is not None and good[b] != bad[b]
               for b in (observe if observe is not None else circuit.outputs.values()))


def all_vectors(circuit):
    """仅用于独立 oracle/故障仿真；ATPG 的决策不读取此穷举结果。"""
    for values in product((0, 1), repeat=len(circuit.inputs)):
        yield dict(zip(circuit.inputs, values))


def symbol(good, bad):
    return "X" if good is None or bad is None else "D" if (good, bad) == (1, 0) else "D̅" if (good, bad) == (0, 1) else str(good)
