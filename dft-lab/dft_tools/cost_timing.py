"""第七周：用明确的口径分析 DFT 代价，不把数字仿真误称为 STA。

输入：Yosys / Scan 插入后的 JSON；输出：reports/timing/cost_timing.json。
依赖：Python 标准库。v3 新增，只读设计，不修改网表或时序约束。
单元数量来自真实网表；延迟、坐标是带单位的教学假设，绝非工艺测量。
参考：OpenSTA 的 min/max 路径分析与 Liberty 库；详见 docs/sources.md。
"""
from collections import Counter
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def inventory(path):
    """按实例展开层次统计叶单元；同一模块实例化两次必须计两次。

    不按模块定义直接求和，也不把 Memory 的 1024 位内容算作扫描 DFF。
    这仍是结构计数：SDFF、XOR、NAND2 的物理面积不相同。
    """
    design = json.loads(path.read_text(encoding='utf-8'))
    modules = design['modules']
    roots = [n for n, m in modules.items()
             if int(str(m.get('attributes', {}).get('top', '0')), 2)]
    if len(roots) != 1:
        # 生成器可以只输出一个完整顶层模块；多模块却没 top 时禁止猜测。
        used = {c['type'] for m in modules.values() for c in m.get('cells', {}).values()}
        roots = [n for n in modules if n not in used and modules[n].get('cells')]
    if len(roots) != 1:
        raise ValueError(f'无法唯一确认顶层: {path}: {roots}')
    counts = Counter()

    def visit(name, stack):
        if name in stack:
            raise ValueError(f'递归模块不受支持: {name}')
        for cell in modules[name].get('cells', {}).values():
            kind = cell['type']
            if kind in modules and modules[kind].get('cells'):
                visit(kind, stack + [name])
            else:
                counts[kind] += 1

    visit(roots[0], [])
    return {'top': roots[0], 'leaf_instances': sum(counts.values()),
            'by_type': dict(sorted(counts.items())), 'source': path.relative_to(ROOT).as_posix()}


def timing_budget(period=10., skew=.8, tcq_min=.2, wire_min=.1,
                  tcq_max=.6, logic_max=7.9, setup=.3, hold=.1, uncertainty=.2):
    """示例：正 skew 表示 capture 时钟比 launch 晚到；单位统一为 ns。

    Hold 比较同一个周期的新数据最早到达，Setup 比较下一周期最晚到达。
    ★ 经验点：降频通常改善 setup，却不改变同边沿 hold 不等式。
    未建模 clock reconvergence、PVT/OCV、恢复移除或真实 ICG 时序弧。
    """
    direct_hold = tcq_min + wire_min - skew - hold - uncertainty
    # 低电平透明锁存器在源时钟高电平期间挡住新值；示例 latch+wire=.1ns。
    latch_arrival = period / 2 + .1
    return {'kind': '示例值；解析预算，不是 OpenSTA 或 SDF 签核', 'unit': 'ns',
            'period': period, 'skew': skew, 'uncertainty': uncertainty,
            'direct_hold_slack': round(direct_hold, 3),
            'lockup_hold_slack': round(latch_arrival - skew - hold - uncertainty, 3),
            'capture_setup_slack': round(period + skew - tcq_max - logic_max - setup - uncertainty, 3),
            'formula_hold': 'tCQ_min + tData_min - skew - tHold - uncertainty',
            'formula_setup': 'T + skew - tCQ_max - tData_max - tSetup - uncertainty',
            'lockup_boundary': '还需检查 latch 到接收 FF 的 setup、占空比与源/目的时钟关系。'}


def reorder_example():
    """同一时钟/边沿组内的坐标小例子；Manhattan 距离只是布线代价代理。

    不移动真实DUT，不跨越lock-up边界。实际重排后应重新导出chain map，
    重排已有pattern比特并重跑验证，不能只把连线画短就沿用旧向量。
    """
    points = [(0, 0), (7, 1), (1, 0), (8, 0), (2, 1), (9, 1)]
    before = list(range(len(points)))
    after = sorted(before, key=lambda i: points[i][0])

    def length(order):
        return sum(abs(points[a][0]-points[b][0]) + abs(points[a][1]-points[b][1])
                   for a, b in zip(order, order[1:]))

    return {'kind': '示例坐标；非布局布线工具输出', 'points': points,
            'before': before, 'after': after,
            'length_before': length(before), 'length_after': length(after),
            'unit': '归一化 Manhattan 距离', 'constraint': '仅同一时钟、同一边沿组内重排'}


def main():
    measurements = {}
    for version in ['v0', 'v1', 'v2']:
        candidates = sorted((ROOT/'netlist'/version).glob('*.json'))
        if not candidates:
            raise FileNotFoundError(f'请先生成 {version} 网表')
        measurements[version] = inventory(candidates[0])
    report = {'schema': 'dft-lab.cost-timing.v1', 'counts': measurements,
              'area_nand2_equivalent': None,
              'area_note': '未提供指定工艺 Liberty 面积、宏面积和布局结果；单元数量不可直接换算等效门。',
              'timing': timing_budget(), 'reordering': reorder_example()}
    dest = ROOT/'reports/timing/cost_timing.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS COST_TIMING: 实测结构计数；时序与坐标明确为示例值')


if __name__ == '__main__':
    main()
