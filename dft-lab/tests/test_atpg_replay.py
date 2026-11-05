"""第六周回放验收：算法声称可检测的每一个故障都必须有完整 DUT 证据。

输入真实 ATPG / 扫描报告和逐例日志；不在测试里伪造检测向量。
标准库 unittest；先运行 run_atpg.py --scan-replay，再运行本文件。
"""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FullReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((ROOT/'reports/atpg/summary.json').read_text(encoding='utf-8'))
        cls.report = json.loads((ROOT/'reports/atpg/scan_replay.json').read_text(encoding='utf-8'))
        cls.mapping = json.loads((ROOT/'reports/scan_chains.json').read_text(encoding='utf-8'))['v2']

    def test_all_detected_faults_replayed(self):
        expected = {case['fault'] for case in self.summary['results'] if case['status'] == 'DETECTED'}
        actual = {case['fault'] for case in self.report.get('cases', [])}
        self.assertEqual(actual, expected, '不能用一个代表性故障代替全部可测故障的完整DUT回放')
        self.assertEqual(len(expected), 19)
        self.assertEqual(self.report['detected_replayed_count'], len(expected))
        self.assertEqual(len(self.report['cases']), len(actual), '不能重复某个故障凑满案例数')
        self.assertEqual(set(self.report['skipped_proven_untestable']), {'e/SA0','e/SA1','r/SA0'})

    def test_independent_truth_and_actual_so_logs(self):
        # 本测试直接按原RTL方程求值，不调用fault_sim或ATPG的gate求值函数。
        def outputs(vector, fault=None):
            values = {}
            def put(name, value):
                values[name] = fault[1] if fault and name == fault[0] else value
            for name in 'abcde':
                put(name, vector[name])
            put('p', values['a'] & values['b'])
            put('net_10', 1-values['a'])
            put('q', values['net_10'] & values['c'])
            put('r', values['d'] & values['e'])
            put('reconv', values['p'] | values['q'])
            put('redundant', values['d'] | values['r'])
            return values
        self.assertEqual({c['cut_output'] for c in self.report['cases']}, {'reconv','redundant'})
        for case in self.report['cases']:
            with self.subTest(fault=case['fault']):
                node, stuck = case['fault'].split('/SA')
                good = outputs(case['pattern'])[case['cut_output']]
                bad = outputs(case['pattern'], (node, int(stuck)))[case['cut_output']]
                self.assertNotEqual(good, bad)
                self.assertEqual((case['good_bit'],case['bad_bit']), (good,bad))
                log = (ROOT/case['log']).read_text(encoding='utf-8')
                match = re.search(r'ATPG_SCAN_OBS cycle=(\d+) chain=(\d+) good=([01]) bad=([01])',log)
                self.assertIsNotNone(match)
                self.assertEqual(tuple(map(int,match.groups())),
                                 (case['observation_shift_cycle_zero_based'],case['observation_chain'],good,bad))
                for marker in ['PASS ATPG_SCAN_LOAD cells_per_dut=293',
                               'PASS ATPG_SCAN_UNLOAD cells_per_dut=293 compared_so_bits=586',
                               'PASS ATPG_FULL_DUT_SCAN']:
                    self.assertIn(marker,log)
                self.assertNotIn('FATAL',log)
                self.assertEqual(case['loaded_cells_checked'],293)
                self.assertEqual(case['unloaded_cells_checked'],293)
                self.assertEqual(case['compared_so_bits'],586)
                self.assertTrue((ROOT/case['vcd']).is_file())
        self.assertEqual(self.report['total_compared_so_bits'],19*586)

    def test_each_stimulus_loads_all_293_target_bits(self):
        # 用逐周期移位模型还原mem文件，不复用生成器的反向位置公式。
        for case in self.report['cases']:
            with self.subTest(fault=case['fault']):
                states = [[0]*chain['length'] for chain in self.mapping['chains']]
                rows = (ROOT/case['input_file']).read_text(encoding='ascii').splitlines()
                self.assertEqual(len(rows),74)
                for row in rows:
                    self.assertRegex(row,r'^[01]{4}$')
                    for index in range(4):
                        states[index] = [int(row[3-index])] + states[index][:-1]
                checked = 0
                for chain in self.mapping['chains']:
                    for cell in chain['cells']:
                        expected = 0
                        for index,name in enumerate('abcde'):
                            if f'u_ingress.word_q[{index}]' in cell['aliases']:
                                expected = case['pattern'][name]
                        self.assertEqual(states[chain['index']][cell['position']],expected)
                        checked += 1
                self.assertEqual(checked,293)

    def test_negative_cases_are_real_failures_and_isolated(self):
        expected = {'no_injection':'ATPG_CAPTURE_OR_SHIFT_MISMATCH',
                    'wrong_input':'ATPG_LOAD_MISMATCH',
                    'wrong_observation':'ATPG_CAPTURE_OR_SHIFT_MISMATCH'}
        self.assertEqual({n['name'] for n in self.report['negative_tests']},set(expected))
        positive_vcd = {case['vcd'] for case in self.report['cases']}
        for case in self.report['negative_tests']:
            with self.subTest(negative=case['name']):
                self.assertNotEqual(case['exit_code'],0)
                self.assertEqual(case['status'],'EXPECTED_FAILURE')
                self.assertEqual(case['reason'],expected[case['name']])
                self.assertNotIn(case['vcd'],positive_vcd)
                log = (ROOT/case['log']).read_text(encoding='utf-8')
                self.assertIn('FATAL',log)
                self.assertIn(expected[case['name']],log)
                self.assertNotIn('PASS ATPG_FULL_DUT_SCAN',log)
        self.assertEqual((self.report['fault'],self.report['good_bit'],self.report['bad_bit']),('q/SA1',0,1))


if __name__ == '__main__':
    result = unittest.main(exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)
    print('PASS ATPG_REPLAY_REGRESSION')
