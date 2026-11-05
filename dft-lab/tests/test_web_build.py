"""网页构建证据回归：旧 PASS 不能替修改过的源码或失败子报告背书。

输入为独立临时工程和报告；输出 unittest 结果与最终 PASS 标记。
依赖 Python 标准库，直接运行 python tests/test_web_build.py。
临时副本模拟修改、删除和失败，不写真实 RTL、报告或已交付 HTML。
本测试只检查发布门禁；硬件结论仍由完整 EDA 流水线产生。
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('web_build', ROOT/'web/build.py')
web_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web_build)


class EvidenceSnapshotTests(unittest.TestCase):
    """每个用例从合法快照出发，只改变一个会使验收失效的条件。"""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='dft-web-evidence-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root/'rtl/v0/example.sv'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('module example; endmodule\n', encoding='utf-8')
        self.evidence = {
            'validation-full.json': {
                'status': 'PASS',
                'source_sha256': {'rtl/v0/example.sv': hashlib.sha256(self.source.read_bytes()).hexdigest()},
            },
            'scan/validation.json': {'status': 'PASS'},
            'atpg/scan_replay.json': {'status': 'PASS'},
            'drc/v1.json': {'pass': True},
            'drc/v2.json': {'pass': True},
        }
        for name, report in self.evidence.items():
            if name != 'validation-full.json':
                self.write_file('reports/'+name, json.dumps(report).encode('utf-8'))
        self.write_file('netlist/v2/design.v', b'module design; endmodule\r\n')
        self.write_file('patterns/vector.mem', b'01010\r\n')
        self.write_file('build/scan.vcd', b'$timescale 1ps $end\n')
        self.evidence['validation-full.json']['artifact_sha256'] = {
            path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for folder in ['netlist', 'patterns', 'reports', 'build']
            for path in (self.root/folder).rglob('*') if path.is_file()
        }

    def write_file(self, name, contents):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        return path

    def test_matching_sources_and_passed_reports_are_accepted(self):
        web_build.verify_evidence(self.root, self.evidence)

    def test_changed_source_invalidates_old_pass(self):
        # 原缺口：报告仍写 PASS，但页面将嵌入未重新验证过的电路。
        self.source.write_text('module example; wire changed; endmodule\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '源码已改变，旧 PASS 已过期'):
            web_build.verify_evidence(self.root, self.evidence)

    def test_missing_verified_source_is_rejected(self):
        self.source.unlink()
        with self.assertRaisesRegex(ValueError, '已验源码文件缺失'):
            web_build.verify_evidence(self.root, self.evidence)

    def test_new_source_in_any_verified_directory_is_rejected(self):
        for folder in ['rtl', 'tb', 'scripts', 'dft_tools', 'constraints', 'tests']:
            with self.subTest(folder=folder):
                path = self.write_file(folder+'/unverified.py', b'# added after PASS\n')
                with self.assertRaisesRegex(ValueError, '源码文件集合已改变'):
                    web_build.verify_evidence(self.root, self.evidence)
                path.unlink()

    def test_changed_netlist_invalidates_old_pass(self):
        self.write_file('netlist/v2/design.v', b'module design; wire changed; endmodule\n')
        with self.assertRaisesRegex(ValueError, '生成物已改变，旧 PASS 已过期'):
            web_build.verify_evidence(self.root, self.evidence)

    def test_changed_pass_report_invalidates_old_pass(self):
        self.evidence['scan/validation.json']['changed_after_validation'] = True
        self.write_file('reports/scan/validation.json', json.dumps(self.evidence['scan/validation.json']).encode('utf-8'))
        with self.assertRaisesRegex(ValueError, '生成物已改变，旧 PASS 已过期'):
            web_build.verify_evidence(self.root, self.evidence)

    def test_missing_pattern_is_rejected(self):
        (self.root/'patterns/vector.mem').unlink()
        with self.assertRaisesRegex(ValueError, '已验生成物文件缺失'):
            web_build.verify_evidence(self.root, self.evidence)

    def test_missing_artifact_snapshot_is_rejected(self):
        for invalid in [None, {}]:
            with self.subTest(snapshot=invalid):
                self.evidence['validation-full.json']['artifact_sha256'] = invalid
                with self.assertRaisesRegex(ValueError, '缺少生成物哈希快照'):
                    web_build.verify_evidence(self.root, self.evidence)

    def test_new_artifact_is_rejected(self):
        for folder in ['netlist', 'patterns', 'reports', 'build']:
            with self.subTest(folder=folder):
                path = self.write_file(folder+'/unverified.txt', b'new artifact\n')
                with self.assertRaisesRegex(ValueError, '生成物文件集合已改变'):
                    web_build.verify_evidence(self.root, self.evidence)
                path.unlink()

    def test_caches_and_independent_ui_reports_do_not_change_snapshot(self):
        for name in ['build/__pycache__/temp', 'build/compiled.vvp', 'netlist/cached.pyc',
                     'reports/validation-full.json', 'reports/validation-web.json',
                     'reports/validation-learning-ui.json', 'tests/__pycache__/cached.pyc']:
            self.write_file(name, b'excluded from hardware snapshot\n')
        web_build.verify_evidence(self.root, self.evidence)

    def test_missing_snapshot_is_rejected(self):
        for invalid in [None, {}]:
            with self.subTest(snapshot=invalid):
                self.evidence['validation-full.json']['source_sha256'] = invalid
                with self.assertRaisesRegex(ValueError, '缺少源码哈希快照'):
                    web_build.verify_evidence(self.root, self.evidence)

    def test_running_or_failed_pipeline_is_rejected(self):
        for status in ['RUNNING', 'FAIL']:
            with self.subTest(status=status):
                self.evidence['validation-full.json']['status'] = status
                with self.assertRaisesRegex(ValueError, '完整工程尚未通过'):
                    web_build.verify_evidence(self.root, self.evidence)

    def test_failed_scan_or_atpg_report_is_rejected(self):
        # 单独重新运行子流程失败，不一定会更新历史总报告；不能只相信总 PASS。
        for name in ['scan/validation.json', 'atpg/scan_replay.json']:
            with self.subTest(report=name):
                evidence = deepcopy(self.evidence)
                evidence[name]['status'] = 'FAIL'
                with self.assertRaisesRegex(ValueError, '必要子报告未通过'):
                    web_build.verify_evidence(self.root, evidence)

    def test_failed_drc_report_is_rejected(self):
        for name in ['drc/v1.json', 'drc/v2.json']:
            with self.subTest(report=name):
                evidence = deepcopy(self.evidence)
                evidence[name]['pass'] = False
                with self.assertRaisesRegex(ValueError, '必要 DRC 报告未通过'):
                    web_build.verify_evidence(self.root, evidence)

    def test_snapshot_must_use_project_relative_paths(self):
        for key in ['source_sha256', 'artifact_sha256']:
            for name in ['../outside.sv', str(self.source.resolve())]:
                with self.subTest(snapshot=key, path=name):
                    evidence = deepcopy(self.evidence)
                    evidence['validation-full.json'][key] = {name: 'unused'}
                    with self.assertRaisesRegex(ValueError, '工程内相对路径'):
                        web_build.verify_evidence(self.root, evidence)


if __name__ == '__main__':
    result = unittest.main(exit=False)
    if not result.result.wasSuccessful():
        raise SystemExit(1)
    print('PASS WEB_BUILD_REGRESSION')
