"""本课程连接级DFT规则检查；不模拟商业DRC的全部规则。

输入真实flat JSON以及链映射；按test_mode=1、test_te=1追溯测试控制。
检查可控时钟/复位、SE、扫描拓扑、边沿顺序、跨域lockup、memory隔离。
增强：拒绝多个输出/外部输入争用同一bit；从v0独立核对每个FF的功能连接和参数。
⚠ 零错误只说明下列已实现规则通过；不覆盖模拟毛刺、setup/hold、功耗或ATPG约束。
"""
import json
from pathlib import Path
from netlist_model import ROOT, flatten, load, registers


def drivers_by_bit(module):
    """保留每个驱动身份，不能用字典赋值把之前的输出脚悄悄覆盖。

    本课只有单向端口；顶层input是外部驱动，output只是观察端而不是新驱动。
    网名别名不新增驱动。Yosys常量字符串也不是可被单元驱动的网络bit。
    """
    drivers = {}
    for name, port in module['ports'].items():
        if port['direction'] == 'input':
            for index, bit in enumerate(port['bits']):
                if isinstance(bit, int):
                    drivers.setdefault(bit, []).append((f'input {name}[{index}]', None))
    for name, cell in module['cells'].items():
        for port, direction in cell['port_directions'].items():
            if direction == 'output':
                for index, bit in enumerate(cell['connections'][port]):
                    if isinstance(bit, int):
                        drivers.setdefault(bit, []).append((f'{name}.{port}[{index}]', cell))
    return drivers


def audit_preservation(original, module, mapping):
    """从真实v0核对每个原FF，不能把插链器写出的mapping元数据当黄金参考。

    输入original是与插链器相同编号体系的flatten v0，module是当前扫描网表。
    返回标准违例列表；不修改任何输入。本检查证明明确列出的pin/参数保留，
    不等价整颗电路的形式等价检查，也没有检查所有组合门的布尔等价性。
    """
    expected = {reg['name']: reg for reg in registers(original)}
    drivers = drivers_by_bit(module)
    mode = module['ports']['test_mode']['bits']
    seen, violations = set(), []

    def issue(rule, name, detail):
        violations.append({'rule': rule, 'severity': 'error', 'cell': name, 'detail': detail})

    for chain in mapping['chains']:
        for entry in chain['cells']:
            source, name = entry['name'], entry['instance']
            if source not in expected or source in seen:
                issue('FF_REFERENCE_INVALID', name, f'原FF身份不存在或重复映射: {source}')
                continue
            seen.add(source)
            reg = expected[source]
            cell = module['cells'].get(name, {})
            if cell.get('type') != 'dft_scan_dff':
                issue('FF_REPLACEMENT_MISSING', name, f'原FF {source} 没有对应SDFF')
                continue
            con, params = cell['connections'], cell['parameters']
            for pin, field in [('Q', 'q'), ('D', 'd'), ('E', 'enable')]:
                if con.get(pin) != [reg[field]]:
                    issue(f'FF_{pin}_CHANGED', name, f'{pin}应保留v0 bit {reg[field]}，实际{con.get(pin)}')
            for parameter, value in [('RESET_VALUE', reg['reset_value']),
                                     ('NEGATIVE', int(reg['edge'] == 'negative'))]:
                if params.get(parameter) != value:
                    issue('FF_'+parameter+'_CHANGED', name, f'{parameter}应为{value}，实际{params.get(parameter)}')
            for pin, field in [('C', 'clock'), ('R', 'reset')]:
                # 本插入方案要求test_mode=0选MUX.A；测试支路由check中的可达性规则另查。
                producers = drivers.get(con[pin][0], [])
                mux = producers[0][1] if len(producers) == 1 else None
                if (not mux or mux['type'] != '$_MUX_' or
                        mux['connections']['S'] != mode or mux['connections']['A'] != [reg[field]]):
                    issue('FF_FUNCTIONAL_'+field.upper()+'_CHANGED', name,
                          f'功能{field}应通过test_mode MUX的A端回到v0 bit {reg[field]}')
    for source in sorted(set(expected)-seen):
        issue('FF_REFERENCE_MISSING', source, '原FF未被链映射覆盖，不能宣称功能状态完整保留')
    return violations


def check(module, version, mapping=None, original=None):
    violations = []
    ports, cells = module['ports'], module['cells']
    all_drivers = drivers_by_bit(module)
    contested = {bit for bit, entries in all_drivers.items() if len(entries) > 1}
    # 只允许唯一的单元输出参与控制锥推导。多驱动既要报错，也不能任选最后一个。
    drivers = {bit: entries[0] for bit, entries in all_drivers.items()
               if len(entries) == 1 and entries[0][1] is not None}

    def issue(rule, cell, detail, severity='error'):
        violations.append({'rule': rule, 'severity': severity, 'cell': cell, 'detail': detail})

    for bit in sorted(contested):
        issue('MULTIPLE_DRIVERS', f'bit {bit}', '同一网络存在多个驱动: '+
              '；'.join(name for name, _ in all_drivers[bit]))
    if original is not None and version != 'v0':
        violations.extend(audit_preservation(original, module, mapping))

    if version == 'v0':
        roots = {ports[n]['bits'][0] for n in ['sys_clk', 'aux_clk']}
        reset = ports['rst_n_ext']['bits'][0]
        for reg in registers(module):
            if reg['clock'] not in roots:
                issue('CLOCK_NOT_TEST_CONTROLLABLE', reg['name'], '内部派生/门控时钟没有测试接管路径')
            if reg['reset'] != reset:
                issue('RESET_NOT_TEST_CONTROLLABLE', reg['name'], '内部异步复位未接test MUX')
        issue('SCAN_PORTS_MISSING', 'top', 'v0未提供SI/SO/SE测试端口')
        issue('MEMORY_X_BOUNDARY', 'u_memory', 'memory输出X可进入shadow逻辑；无写保护/旁路', 'warning')
    else:
        values = {ports[p]['bits'][0]: value for p, value in
                  [('test_mode', 1), ('test_te', 1), ('scan_clk', 'scan_clk'),
                   ('test_rst_n', 'test_rst_n'), ('scan_en', 'scan_en')]}
        if 'scan_clk_aux' in ports:
            values[ports['scan_clk_aux']['bits'][0]] = 'scan_clk_aux'

        def resolve(bit, active=None):
            """只解释测试控制锥；无法确定的功能数据返回unknown，不能当0蒙混。"""
            if bit in contested:
                return 'unknown'
            if bit in ['0', '1']:
                return int(bit)
            if bit in values:
                return values[bit]
            active = set() if active is None else active
            if bit in active or bit not in drivers:
                return 'unknown'
            _, cell = drivers[bit]
            active = active | {bit}
            c, kind = cell['connections'], cell['type']
            get = lambda p: resolve(c[p][0], active)
            if kind == '$_MUX_':
                select = get('S')
                return get('B' if select == 1 else 'A') if select in [0, 1] else 'unknown'
            if kind == 'dft_test_gate':
                return get('CK') if get('TE') == 1 else 'unknown'
            if kind == '$_NOT_':
                a = get('A')
                return 1-a if a in [0, 1] else 'unknown'
            if kind == '$_AND_':
                a, b = get('A'), get('B')
                return 0 if 0 in [a, b] else b if a == 1 else a if b == 1 else 'unknown'
            return 'unknown'

        scanned = {n: c for n, c in cells.items() if c['type'] == 'dft_scan_dff'}
        seen = set()
        for chain in mapping['chains']:
            previous_q = ports['scan_in']['bits'][chain['index']]
            positive_seen = False
            previous_clock = None
            for entry in chain['cells']:
                name = entry['instance']
                if name not in scanned:
                    issue('SCAN_CELL_MISSING', name, '链映射的实例在网表中不存在')
                    continue
                if name in seen:
                    issue('SCAN_CELL_DUPLICATE', name, '同一个SDFF出现在多处链位置')
                seen.add(name)
                cell, con = scanned[name], scanned[name]['connections']
                if resolve(con['C'][0]) not in ['scan_clk', 'scan_clk_aux']:
                    issue('CLOCK_NOT_TEST_CONTROLLABLE', name, '时钟测试支路无法到达scan clock')
                if resolve(con['R'][0]) != 'test_rst_n':
                    issue('RESET_NOT_TEST_CONTROLLABLE', name, '复位测试支路未到达外部test_rst_n')
                if resolve(con['SE'][0]) != 'scan_en':
                    issue('SCAN_ENABLE_BROKEN', name, '测试模式下SE未连接scan_en')
                negative = cell['parameters']['NEGATIVE'] == 1
                if negative and positive_seen:
                    issue('EDGE_ORDER', name, '本课先正沿后负沿的shift协议要求N单元在P单元之前')
                positive_seen |= not negative
                source = con['SI'][0]
                clock = resolve(con['C'][0])
                latch = drivers.get(source, ('', {}))[1]
                crosses = previous_clock is not None and previous_clock != clock
                if crosses:
                    if latch.get('type') != 'dft_lockup_latch' or latch['connections']['D'] != [previous_q]:
                        issue('LOCKUP_MISSING', name, '跨测试时钟域缺少前级Q→低透明lockup→SI')
                    elif resolve(latch['connections']['C'][0]) != previous_clock:
                        issue('LOCKUP_CLOCK', name, 'lockup必须使用前级launch时钟')
                elif source != previous_q:
                    issue('SCAN_LINK_BROKEN', name, 'SI未连接到前一SDFF的Q')
                previous_q, previous_clock = con['Q'][0], clock
            if ports['scan_out']['bits'][chain['index']] != previous_q:
                issue('SCAN_OUT_BROKEN', str(chain['index']), 'SO未连接该链末端Q')
        if seen != set(scanned):
            issue('SCAN_COMPLETENESS', 'top', '存在未列入任何链的SDFF')
        if registers(module):
            issue('NONSCAN_FF', 'top', '存在未替换的原DFF')
        for name, cell in cells.items():
            if cell['type'] != 'packet_mem':
                continue
            if version == 'v2':
                if resolve(cell['connections']['we'][0]) != 0:
                    issue('MEMORY_WRITE_UNGUARDED', name, 'test_mode=1时memory写使能不是常0')
                for index, raw in enumerate(cell['connections']['rdata']):
                    sinks = [(n, p, c) for n, c in cells.items() for p, bs in c['connections'].items()
                             if c['port_directions'][p] == 'input' and raw in bs]
                    if len(sinks) != 1 or sinks[0][2]['type'] != '$_MUX_' or sinks[0][1] != 'A':
                        issue('MEMORY_BYPASS_BROKEN', name, f'原始memory位{index}存在未经过旁路的扇出')
                    else:
                        bypass = sinks[0][2]['connections']
                        if bypass['S'] != ports['test_mode']['bits'] or bypass['B'] != [ports['test_bypass_data']['bits'][index]]:
                            issue('MEMORY_BYPASS_CONTROL', name, f'旁路位{index}测试选择/数据接错')
            else:
                issue('MEMORY_X_BOUNDARY', name, 'v1允许memory X；v2才增加写保护和输出旁路', 'warning')
    errors = sum(v['severity'] == 'error' for v in violations)
    report = {'version': version, 'pass': errors == 0, 'counts': {'errors': errors, 'warnings': len(violations)-errors},
              'violations': violations,
              'scope': '本课程单向端口连接级规则；不等价商业DFT DRC或物理setup/hold签核'}
    if original is not None and version != 'v0':
        report['functional_preservation'] = {
            'reference': 'netlist/v0/design.json', 'register_count': len(registers(original)),
            'scope': '逐FF核对Q/D/E、复位值、触发沿与功能时钟/复位MUX；非整芯片形式等价证明'}
    return report


def main():
    directory = ROOT/'reports/drc'
    directory.mkdir(parents=True, exist_ok=True)
    mapping = load(ROOT/'reports/scan_chains.json')
    original = flatten(load())
    for version in ['v0', 'v1', 'v2']:
        module = original if version == 'v0' else next(iter(load(ROOT/f'netlist/{version}/design.json')['modules'].values()))
        report = check(module, version, mapping.get(version), original)
        (directory/f'{version}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('DRC', version, report['counts'])
        if version != 'v0' and not report['pass']:
            raise SystemExit('DFT DRC失败，停止后续测试')
    print('PASS DFT_DRC')


if __name__ == '__main__':
    main()
