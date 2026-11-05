"""读取真实 Yosys JSON，并按端口连接展开层次。

输入是 synth_v0.ys 的 JSON；输出仍保留 Yosys 的 bits/cells/ports 结构。
bit 编号只在所属 module 内有效，展开时必须重编号，不能直接拼接字典。
本工具支持本课程实际出现的通用门、DFF/DFFE、低透明 latch 与 memory 黑盒。
不支持的单元必须报错，不猜测工业库单元语义。v3 ATPG 可独立读取原始锥。
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path=ROOT / 'netlist/v0/design.json'):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def flatten(design, top='dft_demo_top'):
    """先绑定父子端口，再为局部网络分配全局编号；常量字符串保持原样。"""
    modules = design['modules']
    result = {'attributes': {'top': '1'}, 'ports': {}, 'cells': {}, 'netnames': {}}
    next_bit = 2
    redirects = {}

    def canonical(bit):
        while bit in redirects:
            bit = redirects[bit]
        return bit

    def join(left, right):
        left, right = canonical(left), canonical(right)
        if left != right:
            # 子模块可能把输出直接别名到输入；父级两根线必须真正连起来。
            if isinstance(left, str):
                redirects[right] = left
            else:
                redirects[left] = right

    def visit(name, prefix, mapping):
        nonlocal next_bit
        module = modules[name]

        def mapped(bit):
            nonlocal next_bit
            if isinstance(bit, str):
                return bit
            if bit not in mapping:
                mapping[bit] = next_bit
                next_bit += 1
            return mapping[bit]

        for port, entry in module['ports'].items():
            bits = [mapped(b) for b in entry['bits']]
            if not prefix:
                result['ports'][port] = {**entry, 'bits': bits}
        for net, entry in module['netnames'].items():
            result['netnames'][prefix + net] = {**entry, 'bits': [mapped(b) for b in entry['bits']]}
        for cell_name, entry in module.get('cells', {}).items():
            cell = deepcopy(entry)
            cell['connections'] = {p: [mapped(b) for b in bs] for p, bs in cell['connections'].items()}
            kind = cell['type']
            if kind in modules and modules[kind].get('cells'):
                child_map = {}
                for port, value in modules[kind]['ports'].items():
                    for local, parent in zip(value['bits'], cell['connections'][port]):
                        if isinstance(local, int):
                            if local in child_map:
                                join(child_map[local], parent)
                            else:
                                child_map[local] = parent
                        else:
                            join(parent, local)
                visit(kind, prefix + cell_name + '.', child_map)
            else:
                result['cells'][prefix + cell_name] = cell

    visit(top, '', {})
    for entry in list(result['ports'].values()) + list(result['netnames'].values()):
        entry['bits'] = [canonical(b) for b in entry['bits']]
    for cell in result['cells'].values():
        cell['connections'] = {p: [canonical(b) for b in bs] for p, bs in cell['connections'].items()}
    return result


def aliases(module):
    """只返回可读 RTL 名称；生成器临时网络不会污染课程文件追踪。"""
    found = {}
    for name, net in module['netnames'].items():
        if net.get('hide_name') or '$' in name:
            continue
        for index, bit in enumerate(net['bits']):
            label = name if len(net['bits']) == 1 else f'{name}[{index + net.get("offset", 0)}]'
            found.setdefault(bit, []).append(label)
    return found


def registers(module):
    """明确解码实际的 Yosys 单元名：时钟沿、复位极性和值、enable极性。"""
    names = aliases(module)
    supported = {'$_DFFE_PN0P_', '$_DFF_NN0_', '$_DFF_PN0_', '$_DFF_PN1_'}
    rows = []
    for name, cell in module['cells'].items():
        kind = cell['type']
        if not kind.startswith('$_DFF'):
            continue
        if kind not in supported:
            raise ValueError(f'尚未实现的触发器语义: {kind}')
        con = cell['connections']
        flags = kind.split('_')[2]
        rows.append({'name': name, 'q': con['Q'][0], 'd': con['D'][0],
                     'clock': con['C'][0], 'reset': con['R'][0],
                     'edge': 'negative' if flags[0] == 'N' else 'positive',
                     'reset_value': int(flags[2]), 'enable': con.get('E', ['1'])[0],
                     'aliases': names.get(con['Q'][0], []), 'original_type': kind})
    return rows


def inventory(module):
    regs = registers(module)
    names = aliases(module)
    return {'cell_counts': dict(sorted(Counter(c['type'] for c in module['cells'].values()).items())),
            'register_count': len(regs), 'negative_edge_count': sum(r['edge'] == 'negative' for r in regs),
            'clock_groups': [{'bit': bit, 'aliases': names.get(bit, []), 'count': count}
                             for bit, count in Counter(r['clock'] for r in regs).items()],
            'reset_groups': [{'bit': bit, 'aliases': names.get(bit, []), 'count': count}
                             for bit, count in Counter(r['reset'] for r in regs).items()],
            'memory_instances': [n for n, c in module['cells'].items() if c['type'] == 'packet_mem'],
            'registers': regs}
