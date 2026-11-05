"""完整教学工程的唯一流水线入口：任何必要步骤失败即停止。

输入为 RTL、TB 与网表工具源码；输出日志、网表、pattern 和真实验收报告。
依赖 Python 3、Icarus Verilog / VVP、Yosys。支持路径参数，不硬编码机器目录。
v3 新增：顺序执行 v0 → 扫描改造 → ATPG 回放 → 代价分析，避免并发写同一产物。
网页动画不参与硬件验收；页面构建在全部工程步骤通过后独立执行。
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def snapshot_paths(root, artifacts=False):
    """流水线与网页共用文件集合规则，避免新增文件逃过历史快照检查。"""
    folders = ['netlist', 'patterns', 'reports', 'build'] if artifacts else ['rtl', 'tb', 'scripts', 'dft_tools', 'constraints', 'tests']
    excluded = {'reports/validation-full.json', 'reports/validation-web.json', 'reports/validation-learning-ui.json'}
    files = {}
    for folder in folders:
        for path in sorted((root/folder).rglob('*')):
            relative = path.relative_to(root).as_posix()
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            if artifacts and (path.suffix.lower() in {'.pyc', '.vvp'} or relative in excluded):
                continue
            files[relative] = path
    return files


def main():
    parser = argparse.ArgumentParser(description='按依赖顺序重跑七周 DFT 教学工程')
    parser.add_argument('--iverilog', default='iverilog')
    parser.add_argument('--vvp', default='vvp')
    parser.add_argument('--yosys', default='yosys')
    args = parser.parse_args()
    destination = ROOT/'reports/validation-full.json'
    log_dir = ROOT/'reports/pipeline'
    log_dir.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'dft-lab.validation.full.v1', 'status': 'RUNNING',
              'scope': '七周开源教学工程；不含工艺 STA、全芯片 ATPG 或制造签核',
              'steps': [], 'source_sha256': {}, 'artifact_sha256': {}}
    # 工具检查前就使旧 PASS 失效；缺工具或运行中被终止均不能沿用旧成功结论。
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    executables = {}
    for name in ['iverilog', 'vvp', 'yosys']:
        found = shutil.which(getattr(args, name))
        if not found:
            report['status'] = 'FAIL'
            destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            raise SystemExit(f'缺少 {name}：请安装并加入 PATH，或传 --{name} 完整路径。')
        executables[name] = str(Path(found).resolve())
    env = dict(os.environ)
    env['PYTHONUTF8'] = '1'
    # Windows 的 Icarus 会启动内部 ivl；其 DLL 也要能从 bin 目录发现。
    env['PATH'] = os.pathsep.join(dict.fromkeys(str(Path(p).parent) for p in executables.values())) + os.pathsep + env.get('PATH', '')
    sim_args = ['--iverilog', executables['iverilog'], '--vvp', executables['vvp']]
    jobs = [
        ('v0 功能回归', ['scripts/run.py', 'sim', *sim_args], 'PASS FUNCTIONAL_V0'),
        ('v0 五类结构实验', ['scripts/run.py', 'structures', *sim_args], 'PASS STRUCTURES_V0'),
        ('第二周真实 VCD 快照', ['scripts/study_report.py'], 'PASS WEEK2_EVIDENCE'),
        ('Yosys 综合与冗余结构检查', ['scripts/run.py', 'synth', '--yosys', executables['yosys']], 'PASS NETLIST_STRUCTURE'),
        ('DRC / 全 DUT 单链多链 / 功能与变异验证', ['scripts/run_scan.py', *sim_args], 'PASS SCAN_VALIDATION'),
        ('DRC 负向与功能保持回归', ['tests/test_drc.py'], 'PASS DRC_REGRESSION'),
        ('v1 生成网表的 Yosys 重读检查', [executables['yosys'], '-s', 'scripts/synth_v1.ys'], 'Found and reported 0 problems.'),
        ('v2 生成网表的 Yosys 重读检查', [executables['yosys'], '-s', 'scripts/synth_v2.ys'], 'Found and reported 0 problems.'),
        ('ATPG / 故障仿真 / 全链向量回放', ['scripts/run_atpg.py', '--scan-replay', *sim_args], 'PASS ATPG_ORACLE'),
        ('ATPG 全部可检出故障回放回归', ['tests/test_atpg_replay.py'], 'PASS ATPG_REPLAY_REGRESSION'),
        ('结构代价与教学时序预算', ['dft_tools/cost_timing.py'], 'PASS COST_TIMING'),
        ('网页证据快照回归', ['tests/test_web_build.py'], 'PASS WEB_BUILD_REGRESSION'),
        ('流水线失败与旧 PASS 隔离回归', ['tests/test_pipeline.py'], 'PASS PIPELINE_REGRESSION'),
    ]
    for index, (name, arguments, required_marker) in enumerate(jobs, 1):
        started = time.monotonic()
        command = arguments if arguments[0] == executables['yosys'] else [sys.executable, *arguments]
        process = subprocess.run(command, cwd=ROOT, env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 encoding='utf-8', errors='replace')
        log = log_dir/f'{index:02}.log'
        log.write_text(process.stdout, encoding='utf-8')
        passed = process.returncode == 0 and required_marker in process.stdout
        report['steps'].append({'name': name, 'status': 'PASS' if passed else 'FAIL',
                                'returncode': process.returncode,
                                'seconds': round(time.monotonic()-started, 3),
                                'log': log.relative_to(ROOT).as_posix(),
                                'pass_lines': [line for line in process.stdout.splitlines() if line.startswith('PASS')]})
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)
        if not passed:
            report['status'] = 'FAIL'
            destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(process.stdout[-6000:])
            raise SystemExit(process.returncode or 1)
    # 同时绑定源文件和实际产物；排除总报告自身与独立网页验收，避免循环依赖。
    for key, artifacts in [('source_sha256', False), ('artifact_sha256', True)]:
        report[key] = {name: hashlib.sha256(path.read_bytes()).hexdigest()
                       for name, path in snapshot_paths(ROOT, artifacts).items()}
    report['status'] = 'PASS'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS DFT_FULL_PIPELINE', flush=True)


if __name__ == '__main__':
    main()
