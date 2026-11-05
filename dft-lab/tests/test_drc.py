"""DRC增强回归：让曾被漏报的真实错误成为可重复的失败样本。

输入为现有v0/v1/v2 JSON和scan_chains.json，仅在deepcopy中制造错误。
不改交付网表、不启动商业工具；使用Python标准库unittest。
检查静态规则本身，不声称由这些测试完成物理时序或全芯片等价证明。
运行：python tests/test_drc.py；成功后打印PASS DRC_REGRESSION。
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'dft_tools'))
from drc import audit_preservation, check
from netlist_model import flatten, load


class DRCRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = flatten(load(ROOT/'netlist/v0/design.json'))
        cls.mappings = load(ROOT/'reports/scan_chains.json')
        cls.versions = {v: next(iter(load(ROOT/f'netlist/{v}/design.json')['modules'].values()))
                        for v in ['v1', 'v2']}

    def setUp(self):
        # 每个测试隔离自己的变异，避免前一个错误污染后一个判据。
        self.module = deepcopy(self.versions['v2'])
        self.mapping = deepcopy(self.mappings['v2'])
        self.entry = self.mapping['chains'][0]['cells'][0]
        self.cell = self.module['cells'][self.entry['instance']]

    def assert_rule(self, rule):
        report = check(self.module, 'v2', self.mapping, self.original)
        self.assertFalse(report['pass'])
        self.assertIn(rule, [v['rule'] for v in report['violations']])
        return report

    def test_clean_versions_and_original_diagnostics(self):
        """加强规则不能把正确网表误报，也不能改变v0已有问题的计数口径。"""
        self.assertEqual(check(self.original, 'v0')['counts'], {'errors': 278, 'warnings': 1})
        for version, warnings in [('v1', 1), ('v2', 0)]:
            with self.subTest(version=version):
                report = check(self.versions[version], version, self.mappings[version], self.original)
                self.assertEqual(report['counts'], {'errors': 0, 'warnings': warnings})
                self.assertEqual(report['functional_preservation']['register_count'], 293)
                self.assertEqual(audit_preservation(self.original, self.versions[version], self.mappings[version]), [])

    def test_two_cell_outputs_cannot_drive_one_bit(self):
        """复现旧bug：drivers[bit]=cell曾覆盖前一个驱动并错误报告PASS。"""
        name, cell = next((n, c) for n, c in self.module['cells'].items() if c['type'] == '$_AND_')
        self.module['cells']['mutation_second_driver'] = deepcopy(cell)
        report = self.assert_rule('MULTIPLE_DRIVERS')
        detail = next(v['detail'] for v in report['violations'] if v['rule'] == 'MULTIPLE_DRIVERS')
        self.assertIn(name, detail)
        self.assertIn('mutation_second_driver', detail)

    def test_input_and_cell_output_cannot_compete(self):
        """外部scan_clk已有驱动；内部单元再驱动同bit不是一个合法测试时钟来源。"""
        self.module['cells']['mutation_clock_driver'] = {
            'type': '$_NOT_', 'parameters': {}, 'attributes': {},
            'connections': {'A': self.module['ports']['test_mode']['bits'],
                            'Y': self.module['ports']['scan_clk']['bits']},
            'port_directions': {'A': 'input', 'Y': 'output'}}
        report = self.assert_rule('MULTIPLE_DRIVERS')
        self.assertIn('CLOCK_NOT_TEST_CONTROLLABLE', [v['rule'] for v in report['violations']])

    def test_netname_and_output_alias_are_not_new_drivers(self):
        """同bit的另一个名字或顶层观察输出只增加可读性，不制造第二个源。"""
        bit = self.module['ports']['scan_clk']['bits']
        self.module['netnames']['alias_scan_clock'] = {'bits': bit, 'hide_name': 0, 'attributes': {}}
        self.module['ports']['observe_scan_clock'] = {'bits': bit, 'direction': 'output'}
        self.assertTrue(check(self.module, 'v2', self.mapping, self.original)['pass'])

    def test_functional_d_uses_v0_not_mapping_metadata(self):
        self.cell['connections']['D'] = ['0']
        self.entry['d'] = '0'  # 即便错误生成器同步篡改了mapping，真实v0仍是独立参考。
        self.assert_rule('FF_D_CHANGED')

    def test_functional_enable_is_preserved(self):
        self.cell['connections']['E'] = ['0']
        self.assert_rule('FF_E_CHANGED')

    def test_state_q_identity_is_preserved(self):
        self.cell['connections']['Q'] = [999999]
        self.assert_rule('FF_Q_CHANGED')

    def test_async_reset_value_is_preserved(self):
        self.cell['parameters']['RESET_VALUE'] ^= 1
        self.assert_rule('FF_RESET_VALUE_CHANGED')

    def test_negative_edge_is_preserved(self):
        self.assertEqual(self.cell['parameters']['NEGATIVE'], 1)
        self.cell['parameters']['NEGATIVE'] = 0
        self.assert_rule('FF_NEGATIVE_CHANGED')

    def test_functional_clock_mux_arm_is_preserved(self):
        clock_bit = self.cell['connections']['C']
        mux = next(c for c in self.module['cells'].values()
                   if c['type'] == '$_MUX_' and c['connections']['Y'] == clock_bit)
        mux['connections']['A'] = ['0']
        self.assert_rule('FF_FUNCTIONAL_CLOCK_CHANGED')

    def test_functional_reset_mux_arm_is_preserved(self):
        reset_bit = self.cell['connections']['R']
        mux = next(c for c in self.module['cells'].values()
                   if c['type'] == '$_MUX_' and c['connections']['Y'] == reset_bit)
        mux['connections']['A'] = ['1']
        self.assert_rule('FF_FUNCTIONAL_RESET_CHANGED')

    def test_functional_mux_selector_is_test_mode(self):
        clock_bit = self.cell['connections']['C']
        mux = next(c for c in self.module['cells'].values()
                   if c['type'] == '$_MUX_' and c['connections']['Y'] == clock_bit)
        mux['connections']['S'] = self.module['ports']['test_te']['bits']
        self.assert_rule('FF_FUNCTIONAL_CLOCK_CHANGED')

    def test_missing_original_ff_cannot_hide_in_mapping(self):
        self.mapping['chains'][0]['cells'].pop(0)
        self.assert_rule('FF_REFERENCE_MISSING')


if __name__ == '__main__':
    result = unittest.main(exit=False)
    if not result.result.wasSuccessful():
        raise SystemExit(1)
    print('PASS DRC_REGRESSION')
