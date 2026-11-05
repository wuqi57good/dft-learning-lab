"""第3周结构盘点入口：报告实际FF、时钟、复位、memory与其RTL别名。

依赖 netlist_model；输入 netlist/v0/design.json；输出 reports/drc/inventory.json。
这里统计的是逻辑对象，不把通用单元数误叫成NAND2等效面积。
新增v1/v2报告由scan_insert/drc负责，避免统计和修改混在一个函数。
"""
import json
from netlist_model import ROOT, flatten, inventory, load


def main():
    target = ROOT/'reports/drc'
    target.mkdir(parents=True, exist_ok=True)
    report = inventory(flatten(load()))
    report['source'] = 'netlist/v0/design.json'
    report['area_nand2_equivalent'] = None
    (target/'inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS DFT_INVENTORY', report['register_count'], 'FF')


if __name__ == '__main__':
    main()
