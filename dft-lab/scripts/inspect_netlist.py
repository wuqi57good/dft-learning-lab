"""用途：对实际 JSON 检查教学结构是否存活，并统计通用单元。
输入：netlist/v0/design.json；输出：reports/netlist_inventory.json。
依赖：Python 标准库。v0 仅结构验收，不冒充工业级 DRC 或面积签核。
"""
from pathlib import Path
from collections import Counter
import json

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT/'netlist/v0/design.json').read_text())
modules = data['modules']
counts = Counter()

def visit(name):
    """按实例展开统计；同一模块例化两次应计两次，memory 黑盒单列。"""
    for cell in modules[name].get('cells', {}).values():
        kind = cell['type']
        if kind in modules and not int(modules[kind].get('attributes',{}).get('blackbox','0'),2):
            visit(kind)
        else:
            counts[kind] += 1

visit('dft_demo_top')
cone = modules['fault_cone']
r_bits = set(cone['netnames']['r']['bits'])
a_bits = set(cone['ports']['d']['bits'])
redundant_bits = set(cone['ports']['redundant']['bits'])
# 不仅检查网名还检查驱动：别名存在不代表真实的冗余 AND 门存在。
drivers = [cell for cell in cone['cells'].values()
           if cell['type'] == '$_AND_' and r_bits.intersection(cell['connections']['Y'])]
absorbers = [cell for cell in cone['cells'].values() if cell['type'] == '$_OR_'
            and redundant_bits.intersection(cell['connections']['Y'])
            and r_bits.union(a_bits) == set(cell['connections']['A']+cell['connections']['B'])]
assert drivers and absorbers, '冗余 AND→OR 拓扑被优化：禁止沿用该故障靶点。'
# r 不得与 p 共用节点，也不得从其他门输入获得额外观察通路。
# 只检查 keep 名字不够：综合共享公共子表达式也能让原本的不可测故障变可测。
assert not r_bits.intersection(cone['netnames']['p']['bits']), 'r 与重汇聚支路 p 合并'
consumers = [cell for cell in cone['cells'].values()
             if any(r_bits.intersection(bits) for port,bits in cell['connections'].items()
                    if cell['port_directions'][port] == 'input')]
assert len(consumers) == 1 and consumers[0] in absorbers, 'r 出现额外观察路径'
memory = modules['packet_mem']
assert int(memory.get('attributes',{}).get('blackbox','0'),2), 'memory 必须保持宏黑盒'
report = dict(schema='dft-lab.inventory.v0', generic_cell_counts=dict(sorted(counts.items())),
    generic_cell_total=sum(v for k,v in counts.items() if k!='packet_mem'),
    memory_blackbox_instances=counts['packet_mem'], redundant_branch_preserved=True,
    area_nand2_equivalent=None,
    note='这些是本项目字段；无 Liberty 面积数据，不能换算 NAND2 等效门数。')
(ROOT/'reports/netlist_inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS NETLIST_STRUCTURE: redundant branch retained; memory blackbox retained')
print(json.dumps(report,ensure_ascii=False,indent=2))
