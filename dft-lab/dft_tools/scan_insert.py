"""在真实 Yosys JSON 的寄存器连接上插入扫描能力，写 JSON 和可仿真 Verilog。

输入 netlist/v0/design.json；输出 netlist/v1、v2 和 reports/scan_chains.json。
v1统一测试时钟并串单链；v2四链、测试域lock-up、memory写保护和输出旁路。
不做工艺映射、不删除功能逻辑、不以一组孤立移位寄存器冒充 DUT scan。
所有编号/长度来自输入网表；遇到未知单元拒绝输出，防止悄悄漏扫。
"""
from copy import deepcopy
import json
from pathlib import Path
from netlist_model import ROOT, aliases, flatten, load, registers
from chain_balance import balance


def add_cell(module, name, kind, connections, outputs=('Y',), parameters=None):
    # Yosys的wire/cell共享标识符空间；JSON必须能被read_json重新读入。
    if name in module['netnames']:
        name += '_cell'
    module['cells'][name] = {'hide_name': 0, 'type': kind, 'parameters': parameters or {},
                            'attributes': {}, 'connections': connections,
                            'port_directions': {p: 'output' if p in outputs else 'input' for p in connections}}
    return name


def insert(original, version):
    module = deepcopy(original)
    next_bit = max(b for n in module['netnames'].values() for b in n['bits'] if isinstance(b, int)) + 1

    def allocate(name, width=1, direction=None):
        nonlocal next_bit
        bits = list(range(next_bit, next_bit + width))
        next_bit += width
        module['netnames'][name] = {'hide_name': 0, 'bits': bits, 'attributes': {}}
        if direction:
            module['ports'][name] = {'direction': direction, 'bits': bits}
        return bits

    def mux(name, a, b, select):
        y = allocate(name)
        add_cell(module, name, '$_MUX_', {'A': [a], 'B': [b], 'S': [select], 'Y': y})
        return y[0]

    count = 1 if version == 'v1' else 4
    for port in ['test_mode', 'test_rst_n', 'scan_clk', 'scan_en', 'test_te']:
        allocate(port, direction='input')
    allocate('scan_in', count, 'input')
    allocate('scan_out', count, 'output')
    if version == 'v2':
        allocate('scan_clk_aux', direction='input')
        allocate('test_bypass_data', 32, 'input')
    ports = {p: v['bits'] for p, v in module['ports'].items()}
    mode, scan_clk = ports['test_mode'][0], ports['scan_clk'][0]
    se = allocate('dft_shift_enable')
    add_cell(module, 'dft_shift_enable', '$_AND_', {'A': [mode], 'B': ports['scan_en'], 'Y': se})
    gate = allocate('dft_gated_scan_clock')
    add_cell(module, 'dft_test_gate', 'dft_test_gate', {'CK': [scan_clk], 'TE': ports['test_te'], 'Q': gate}, ('Q',))
    regs = registers(module)
    readable = aliases(module)
    clock_muxes, reset_muxes = {}, {}
    for reg in regs:
        clock_alias = readable.get(reg['clock'], [])
        reg['clock_domain'] = ('aux' if 'aux_clk' in clock_alias else
                               'gate' if 'u_count.gated_clk' in clock_alias else
                               'div' if 'div_clk' in clock_alias else 'sys')
        domain = reg['clock_domain']
        test_clock = gate[0] if domain == 'gate' else ports['scan_clk_aux'][0] if version == 'v2' and domain == 'aux' else scan_clk
        # 🔧 每一个原时钟与复位都经显式 MUX；DRC 可由真实连接追溯其测试支路。
        if reg['clock'] not in clock_muxes:
            clock_muxes[reg['clock']] = mux(f'dft_clock_{domain}', reg['clock'], test_clock, mode)
        if reg['reset'] not in reset_muxes:
            reset_muxes[reg['reset']] = mux(f'dft_reset_{len(reset_muxes)}', reg['reset'], ports['test_rst_n'][0], mode)
        reg['test_clock'] = test_clock
        reg['clock_mux'] = clock_muxes[reg['clock']]
        reg['reset_mux'] = reset_muxes[reg['reset']]

    # v1 保留 memory X 作为下一阶段的未解决问题；v2用外部可控数据旁路。
    # 写保护在整个test_mode有效，不能只在scan_en=1时保护，否则capture仍会误写。
    if version == 'v2':
        not_mode = allocate('dft_functional_mode')
        add_cell(module, 'dft_functional_mode', '$_NOT_', {'A': [mode], 'Y': not_mode})
        for name, cell in list(module['cells'].items()):
            if cell['type'] != 'packet_mem':
                continue
            con = cell['connections']
            guarded = allocate('dft_memory_we')
            add_cell(module, 'dft_memory_write_guard', '$_AND_', {'A': con['we'], 'B': not_mode, 'Y': guarded})
            con['we'] = guarded
            outputs = con['rdata']
            raw = allocate('dft_memory_raw', len(outputs))
            con['rdata'] = raw
            for bit, (source, sink, replacement) in enumerate(zip(raw, outputs, ports['test_bypass_data'])):
                add_cell(module, f'dft_memory_bypass_{bit}', '$_MUX_',
                         {'A': [source], 'B': [replacement], 'S': [mode], 'Y': [sink]})

    chains = balance(regs, count)
    lockups = []
    for chain_index, chain in enumerate(chains):
        upstream = ports['scan_in'][chain_index]
        previous = None
        for position, reg in enumerate(chain):
            if version == 'v2' and previous and previous['test_clock'] != reg['test_clock']:
                # 门控test时钟在TE=1时与主时钟同相，不需要人为为每个gate分组加锁存器。
                source_domain = 'aux' if previous['clock_domain'] == 'aux' else 'main'
                sink_domain = 'aux' if reg['clock_domain'] == 'aux' else 'main'
                if source_domain != sink_domain:
                    if previous['edge'] != 'positive' or reg['edge'] != 'positive':
                        raise ValueError('本课程lockup仅实现正沿→正沿跨域')
                    latch_name = f'dft_lockup_{chain_index}_{position}'
                    held = allocate(latch_name)
                    latch_instance = add_cell(module, latch_name, 'dft_lockup_latch',
                             {'C': [previous['test_clock']], 'D': [upstream], 'Q': held}, ('Q',))
                    lockups.append({'name': latch_instance, 'chain': chain_index, 'before_position': position,
                                    'source_q': upstream, 'held_q': held[0], 'source_clock': previous['test_clock']})
                    upstream = held[0]
            cell_name = f'sdff_{chain_index}_{position}'
            del module['cells'][reg['name']]
            add_cell(module, cell_name, 'dft_scan_dff',
                     {'C': [reg['clock_mux']], 'R': [reg['reset_mux']], 'D': [reg['d']],
                      'E': [reg['enable']], 'SE': se, 'SI': [upstream], 'Q': [reg['q']]}, ('Q',),
                     {'NEGATIVE': int(reg['edge'] == 'negative'), 'RESET_VALUE': reg['reset_value']})
            reg['instance'] = cell_name
            reg['si'] = upstream
            upstream, previous = reg['q'], reg
        # SO是连接别名，不能另造无驱动输出bit。替换端口与同名netname即可。
        ports['scan_out'][chain_index] = upstream
        module['netnames']['scan_out']['bits'][chain_index] = upstream
    mapping = {'top': 'dft_demo_top_' + version, 'version': version,
               'scan_cell_count': len(regs), 'chain_count': count,
               'chains': [{'index': i, 'length': len(c), 'cells': c} for i, c in enumerate(chains)],
               'lockups': lockups, 'excluded': [{'kind': 'packet_mem', 'reason': 'memory宏另有测试流程，不串普通scan'},
                                               {'kind': '$_DLATCH_N_', 'reason': 'ICG enable latch保留功能并由TE测试旁路'}],
               'shift_protocol': '起始所有scan clock=0；SO在正沿前采样；SI稳定后主正沿、aux正沿、主负沿、aux负沿；每一完整周期推进一位',
               'capture_protocol': 'scan_en=0且test_mode=1；test_rst_n=1, test_te=1；先正沿再负沿；非at-speed教学捕获'}
    return module, mapping


def emit_verilog(module, top):
    """只翻译明确支持的门与单元；行为来自同一份JSON，避免JSON/Verilog两套真相。"""
    def bit(value):
        return f'n{value}' if isinstance(value, int) else "1'b" + value

    def bus(values):
        return bit(values[0]) if len(values) == 1 else '{' + ','.join(bit(v) for v in reversed(values)) + '}'

    used = sorted({b for c in module['cells'].values() for v in c['connections'].values() for b in v if isinstance(b, int)} |
                  {b for p in module['ports'].values() for b in p['bits'] if isinstance(b, int)})
    lines = ['// 自动生成：scan_insert.py 从真实 v0 Yosys JSON 插入；禁止手改该产物。',
             '// 单元级连接见同目录design.json；链顺序见reports/scan_chains.json。',
             f'module {top}(' + ','.join(module['ports']) + ');']
    for name, port in module['ports'].items():
        width = '' if len(port['bits']) == 1 else f'[{len(port["bits"])-1}:0] '
        lines.append(f'  {port["direction"]} wire {width}{name};')
    for offset in range(0, len(used), 30):
        lines.append('  wire ' + ','.join(bit(b) for b in used[offset:offset+30]) + ';')
    for name, port in module['ports'].items():
        lhs, rhs = (bus(port['bits']), name) if port['direction'] == 'input' else (name, bus(port['bits']))
        lines.append(f'  assign {lhs} = {rhs};')
    binary = {'$_AND_': '&', '$_OR_': '|', '$_XOR_': '^'}
    for index, (name, cell) in enumerate(module['cells'].items()):
        con, kind = cell['connections'], cell['type']
        get = lambda p: bus(con[p])
        if kind in binary:
            lines.append(f'  assign {get("Y")} = {get("A")} {binary[kind]} {get("B")};')
        elif kind == '$_NOT_':
            lines.append(f'  assign {get("Y")} = ~{get("A")};')
        elif kind == '$_MUX_':
            lines.append(f'  assign {get("Y")} = {get("S")} ? {get("B")} : {get("A")};')
        else:
            params = ''
            if kind == '$_DLATCH_N_':
                kind = 'dft_level_latch'
            elif kind not in {'packet_mem', 'dft_scan_dff', 'dft_test_gate', 'dft_lockup_latch'}:
                raise ValueError(f'无法输出未知单元: {kind}')
            if cell['parameters']:
                params = ' #(' + ','.join(f'.{p}({v})' for p, v in cell['parameters'].items()) + ')'
            instance = name if name.startswith(('sdff_', 'dft_')) else f'cell_{index}'
            lines.append(f'  {kind}{params} {instance}(' + ','.join(f'.{p}({get(p)})' for p in con) + ');')
    lines.append('endmodule')
    return '\n'.join(lines) + '\n'


def main():
    original = flatten(load())
    mappings = {}
    for version in ['v1', 'v2']:
        module, mapping = insert(original, version)
        directory = ROOT / 'netlist' / version
        directory.mkdir(parents=True, exist_ok=True)
        design = {'creator': 'DFT Lab Python scan insertion; input is real Yosys JSON',
                  'modules': {mapping['top']: module}}
        (directory/'design.json').write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding='utf-8')
        (directory/'design.v').write_text(emit_verilog(module, mapping['top']), encoding='utf-8')
        mappings[version] = mapping
    (ROOT/'reports/scan_chains.json').write_text(json.dumps(mappings, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS SCAN_INSERT', {v: [c['length'] for c in m['chains']] for v, m in mappings.items()})


if __name__ == '__main__':
    main()
