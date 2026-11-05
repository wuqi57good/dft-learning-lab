"""隔离复现流水线失败：重跑不能残留上一次的 PASS。

输入为临时目录、旧 PASS 和模拟子进程；输出 unittest 结果及 PASS 标记。
仅依赖 Python 标准库；直接运行 python tests/test_pipeline.py。
所有工具查找与子进程执行均被 mock，不启动 EDA 工具，也不递归运行流水线。
测试检查流程控制与源码快照；真正的电路验收仍由 scripts/run_all.py 执行。
"""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('run_all', ROOT/'scripts/run_all.py')
run_all = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_all)
SUBFLOWS = []
for name, report, arguments in [('run_scan', 'scan/validation.json', []),
                                ('run_atpg', 'atpg/scan_replay.json', ['--scan-replay'])]:
    spec = importlib.util.spec_from_file_location(name, ROOT/f'scripts/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    SUBFLOWS.append((module, report, arguments))


class PipelineFailureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='dft-pipeline-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.destination = self.root/'reports/validation-full.json'
        self.destination.parent.mkdir(parents=True)
        self.write_old_pass()
        patcher = patch.object(run_all, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.argv = patch.object(sys, 'argv', ['run_all.py'])
        self.argv.start()
        self.addCleanup(self.argv.stop)

    def write_old_pass(self):
        self.destination.write_text(json.dumps({
            'status': 'PASS', 'steps': [{'name': 'old-success'}],
            'source_sha256': {'old-source': 'old-hash'},
            'artifact_sha256': {'old-artifact': 'old-hash'},
        }), encoding='utf-8')

    def report(self):
        return json.loads(self.destination.read_text(encoding='utf-8'))

    def run_with_mock(self, execution):
        with patch.object(run_all.shutil, 'which', return_value=sys.executable), \
                patch.object(run_all.subprocess, 'run', side_effect=execution) as mocked, \
                redirect_stdout(io.StringIO()):
            run_all.main()
        return mocked

    def test_interruption_invalidates_old_pass(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_with_mock(KeyboardInterrupt)
        self.assertEqual(self.report()['status'], 'RUNNING')
        self.assertEqual(self.report()['steps'], [])
        self.assertEqual(self.report()['source_sha256'], {})
        self.assertEqual(self.report()['artifact_sha256'], {})

    def test_nonzero_returncode_fails_even_with_pass_marker(self):
        with self.assertRaises(SystemExit) as error:
            self.run_with_mock(lambda *args, **kwargs: subprocess.CompletedProcess(
                args[0], 7, stdout='PASS FUNCTIONAL_V0\n'))
        self.assertEqual(error.exception.code, 7)
        report = self.report()
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(len(report['steps']), 1)
        self.assertEqual(report['steps'][0]['returncode'], 7)
        self.assertEqual(report['steps'][0]['status'], 'FAIL')
        self.assertEqual(report['source_sha256'], {})
        self.assertEqual(report['artifact_sha256'], {})

    def test_zero_returncode_without_required_marker_fails(self):
        with self.assertRaises(SystemExit) as error:
            self.run_with_mock(lambda *args, **kwargs: subprocess.CompletedProcess(
                args[0], 0, stdout='simulation finished, no acceptance marker\n'))
        self.assertEqual(error.exception.code, 1)
        report = self.report()
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(len(report['steps']), 1)
        self.assertEqual(report['steps'][0]['status'], 'FAIL')
        self.assertEqual(report['source_sha256'], {})
        self.assertEqual(report['artifact_sha256'], {})

    def test_missing_tool_invalidates_old_pass_before_any_job(self):
        for missing in ['iverilog', 'vvp', 'yosys']:
            with self.subTest(tool=missing):
                self.write_old_pass()
                with patch.object(run_all.shutil, 'which', side_effect=lambda name:
                                  None if name == missing else sys.executable), \
                        patch.object(run_all.subprocess, 'run') as mocked, \
                        self.assertRaisesRegex(SystemExit, '缺少 ' + missing):
                    run_all.main()
                mocked.assert_not_called()
                self.assertEqual(self.report()['status'], 'FAIL')
                self.assertEqual(self.report()['steps'], [])
                self.assertEqual(self.report()['source_sha256'], {})
                self.assertEqual(self.report()['artifact_sha256'], {})

    def test_success_runs_regressions_and_hashes_tests_without_cache(self):
        source = self.root/'tests/example.py'
        source.parent.mkdir()
        source.write_bytes(b'assert True\r\n')
        cache = self.root/'tests/__pycache__/example.pyc'
        cache.parent.mkdir()
        cache.write_bytes(b'cached bytecode')
        artifacts = {}
        for name in ['netlist/design.v', 'patterns/vector.mem', 'reports/sim.log', 'build/wave.vcd']:
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture bytes\r\n')
            artifacts[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for name in ['build/compiled.vvp', 'build/cache.pyc', 'build/__pycache__/cache',
                     'reports/validation-web.json', 'reports/validation-learning-ui.json']:
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'excluded bytes\n')
        # 每个模拟任务只返回自身的验收标记，检查任务与标记是否正确配对。
        markers = [
            'PASS FUNCTIONAL_V0', 'PASS STRUCTURES_V0', 'PASS WEEK2_EVIDENCE',
            'PASS NETLIST_STRUCTURE', 'PASS SCAN_VALIDATION', 'PASS DRC_REGRESSION',
            'Found and reported 0 problems.', 'Found and reported 0 problems.',
            'PASS ATPG_ORACLE', 'PASS ATPG_REPLAY_REGRESSION',
            'PASS COST_TIMING', 'PASS WEB_BUILD_REGRESSION',
            'PASS PIPELINE_REGRESSION',
        ]
        outputs = iter(markers)
        mocked = self.run_with_mock(lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=next(outputs) + '\n'))
        commands = [call.args[0] for call in mocked.call_args_list]
        self.assertEqual(len(commands), len(markers))
        self.assertIn('scripts/run_scan.py', commands[4])
        self.assertIn('tests/test_drc.py', commands[5])
        self.assertIn('tests/test_atpg_replay.py', commands[9])
        self.assertIn('tests/test_web_build.py', commands[11])
        self.assertIn('tests/test_pipeline.py', commands[12])
        report = self.report()
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['source_sha256'], {
            'tests/example.py': hashlib.sha256(source.read_bytes()).hexdigest(),
        })
        for index in range(1, len(markers)+1):
            name = f'reports/pipeline/{index:02}.log'
            artifacts[name] = hashlib.sha256((self.root/name).read_bytes()).hexdigest()
        self.assertEqual(report['artifact_sha256'], artifacts)
        self.assertTrue(all(step['status'] == 'PASS' for step in report['steps']))

    def test_subflow_missing_tools_invalidates_old_pass(self):
        for module, relative, arguments in SUBFLOWS:
            with self.subTest(entry=module.__name__):
                destination = self.root/'reports'/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text('{"status":"PASS"}', encoding='utf-8')
                with patch.object(module, 'ROOT', self.root), \
                        patch.object(sys, 'argv', [module.__name__, *arguments]), \
                        patch.object(module.shutil, 'which', return_value=None), \
                        patch.object(module.subprocess, 'run') as execute, \
                        redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    module.main()
                execute.assert_not_called()
                self.assertEqual(json.loads(destination.read_text(encoding='utf-8'))['status'], 'RUNNING')

    def test_subflow_first_execution_or_read_failure_invalidates_old_pass(self):
        for module, relative, arguments in SUBFLOWS:
            with self.subTest(entry=module.__name__):
                destination = self.root/'reports'/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text('{"status":"PASS"}', encoding='utf-8')
                target, method = (module.subprocess, 'run') if module.__name__ == 'run_scan' else (module.Circuit, 'load')
                with patch.object(module, 'ROOT', self.root), \
                        patch.object(sys, 'argv', [module.__name__, *arguments]), \
                        patch.object(module.shutil, 'which', return_value=sys.executable), \
                        patch.object(target, method, side_effect=RuntimeError('simulated failure')) as execute, \
                        self.assertRaisesRegex(RuntimeError, 'simulated failure'):
                    module.main()
                execute.assert_called_once()
                self.assertEqual(json.loads(destination.read_text(encoding='utf-8'))['status'], 'RUNNING')


if __name__ == '__main__':
    result = unittest.main(exit=False)
    if not result.result.wasSuccessful():
        raise SystemExit(1)
    print('PASS PIPELINE_REGRESSION')
