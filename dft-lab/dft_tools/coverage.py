"""固定故障分母的覆盖率累计及随机前缀/确定性向量对比。

输入为真实 cut、ATPG 向量；输出每一步新增/累计检测故障。数值只属于本
fault_cone，不包括 scan cell、时钟、memory、SDFF MUX 或整颗 DUT 的故障。
未折叠 fault coverage=detected/全部建模故障；test coverage 的分母排除
已由穷举证明的不可测故障，二者必须分别命名，不能偷偷更换图表分母。
"""
import random
from fault_sim import detected


def coverage_curve(circuit, atpg_results, extra_observe=()):
    rng = random.Random(20261105)
    faults = circuit.faults()
    normal = list(circuit.outputs.values())
    enhanced = normal + list(extra_observe)
    patterns = [("seeded_random", {n: rng.randrange(2) for n in circuit.inputs}) for _ in range(6)]
    # 确定性阶段按真实尚未覆盖的故障选向量；不手填上升曲线，也不改分母。
    seen = {f for _, v in patterns for f in faults if detected(circuit, v, f)}
    seen_extra = {f for _, v in patterns for f in faults if detected(circuit, v, f, enhanced)}
    for result in atpg_results:
        vector, fault = result["pattern"], tuple(result["fault_bits"])
        enhanced_target = result.get("observation") == "with_r_observe"
        if vector is not None and fault not in (seen_extra if enhanced_target else seen):
            patterns.append(("observe_point_atpg" if enhanced_target else "deterministic_atpg", vector))
            seen.update(f for f in faults if detected(circuit, vector, f))
            seen_extra.update(f for f in faults if detected(circuit, vector, f, enhanced))
    covered, improved, points = set(), set(), []
    points.append({"index": 0, "phase": "initial", "pattern": None, "detected": 0,
                   "with_observe": 0, "denominator": len(faults), "percent": 0})
    for index, (phase, vector) in enumerate(patterns, 1):
        found = {f for f in faults if detected(circuit, vector, f, normal)}
        added = sorted(found-covered)
        covered |= found
        improved |= {f for f in faults if detected(circuit, vector, f, enhanced)}
        points.append({"index": index, "phase": phase, "pattern": vector,
                       "new_faults": [circuit.label(f) for f in added],
                       "detected": len(covered), "with_observe": len(improved),
                       "denominator": len(faults), "percent": 100*len(covered)/len(faults)})
    return points
