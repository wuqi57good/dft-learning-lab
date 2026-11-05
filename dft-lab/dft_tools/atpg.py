"""简化 D 算法：路径敏化、门 cube 逆向 justification、冲突撤销与故障验证。

v3 输入由 fault_sim.Circuit 解析的真实网表；输出 PI 向量与逐步搜索轨迹。
这是教学用 D-cube 搜索子集，不是完整工业 D/J-frontier 算法，也不是 PODEM。
通过独立的 32 向量 oracle 证明本项目 cut 的结果，不把本算法的搜索失败
推广成任意电路的不可测证明。普通门的 stem 故障可能沿多个扇出路径传播；
最后必须用独立好/坏电路确认，不能只凭局部敏化约束宣布成功。
"""
from fault_sim import detected, simulate, symbol


def cubes(kind, inputs, output):
    """用最小输入条件解释一个输出目标；省略的输入是真正的 don't-care。

    AND=0 可由任一输入为 0 解释，两个选项必须可以回溯。若强迫两者均 0，
    就可能把本来可测的重汇聚故障误判为无解。此处不读取任何预知测试向量。
    """
    if kind == "$_NOT_":
        return [[(inputs[0], 1-output)]]
    control = 0 if kind == "$_AND_" else 1
    if output == control:
        return [[(bit, control)] for bit in inputs]
    return [[(bit, output) for bit in inputs]]


def generate(circuit, fault, observe=None):
    """先激活 fault，再沿候选路径使旁支取非控制值，并求解所有 PI 条件。

    为便于新人跟踪，每次赋值都复制小字典；工业实现通常使用 implication
    trail 撤销，避免大网表拷贝成本。支持的 cut 很小，因此保留清晰的递归。
    """
    observations = set(observe if observe is not None else circuit.outputs.values())
    drivers = {g["output"]: g for g in circuit.gates}
    pi_names = {b: n for n, b in circuit.inputs.items()}
    trace = []

    def event(action, **fields):
        trace.append({"step": len(trace), "action": action, **fields})

    def paths(bit, walked=()):
        if bit in observations:
            yield []
        for gate in circuit.gates:
            if bit in gate["inputs"] and gate["output"] not in walked:
                for tail in paths(gate["output"], walked+(bit,)):
                    yield [(bit, gate)] + tail

    def finish(assigned, index=0):
        """未约束 PI 仍可影响重汇聚；逐项补齐并做实际故障仿真。

        这里的搜索是已求得 cube 的剩余 PI 决策，不调用枚举 oracle。
        检测失败要继续尝试，不能把 X 随意填 0 后直接丢掉一个有效 cube。
        """
        bits = list(circuit.inputs.values())
        if index == len(bits):
            vector = {n: assigned[b] for n, b in circuit.inputs.items()}
            ok = detected(circuit, vector, fault, observations)
            event("detect" if ok else "masked", vector=vector,
                  reason="好/坏电路在观察点产生确定差异" if ok else "重汇聚使局部差异被屏蔽")
            return vector if ok else None
        bit = bits[index]
        if bit in assigned:
            return finish(assigned, index+1)
        for value in (0, 1):
            event("fill", node=pi_names[bit], value=value)
            result = finish({**assigned, bit: value}, index+1)
            if result is not None:
                return result
        return None

    def justify(goals, assigned):
        if not goals:
            return finish(assigned)
        (bit, target), *rest = goals
        name = circuit.names.get(bit, str(bit))
        if bit in assigned:
            if assigned[bit] != target:
                event("conflict", node=name, existing=assigned[bit], requested=target,
                      reason="同一条物理网线不能同时等于 0 和 1")
                return None
            return justify(rest, assigned)
        event("objective", node=name, value=target)
        branch = {**assigned, bit: target}
        if bit in pi_names:
            event("assign", node=name, value=target)
            partial = {n: branch.get(b) for n, b in circuit.inputs.items()}
            good, bad = simulate(circuit, partial), simulate(circuit, partial, fault)
            event("imply", values={circuit.names[b]: symbol(good[b], bad[b]) for b in circuit.names},
                  reason="根据当前 PI 前向蕴涵；仍未知的节点保留 X")
            return justify(rest, branch)
        if bit in ("0", "1"):
            return justify(rest, branch) if int(bit) == target else None
        gate = drivers[bit]
        for index, cube in enumerate(cubes(gate["kind"], gate["inputs"], target)):
            event("justify", node=name, cube=index,
                  requirements=[{"node": circuit.names.get(b, str(b)), "value": v} for b, v in cube])
            result = justify(cube + rest, branch)
            if result is not None:
                return result
            event("backtrack", node=name, cube=index, reason="撤销此分支产生的赋值，改试另一输入解释")
        return None

    for path in paths(fault[0]):
        event("path", nodes=[circuit.names[fault[0]]] + [circuit.names[g["output"]] for _, g in path])
        goals = [(fault[0], 1-fault[1])]
        for incoming, gate in path:
            if gate["kind"] != "$_NOT_":
                noncontrol = 1 if gate["kind"] == "$_AND_" else 0
                goals += [(bit, noncontrol) for bit in gate["inputs"] if bit != incoming]
        vector = justify(goals, {})
        if vector is not None:
            return {"status": "DETECTED", "pattern": vector, "trace": trace}
    event("exhausted", reason="当前路径/cube 搜索范围已耗尽；需独立证明才能称为不可测")
    return {"status": "SEARCH_EXHAUSTED", "pattern": None, "trace": trace}
