"""用途：从任何工作目录启动 v0 仿真或综合，保存真实日志。
输入：工程 RTL / 综合脚本；输出：build、netlist、reports。
依赖：Python 标准库 + PATH 中的 iverilog/vvp/yosys；可用工具参数指定路径。
演进：第一周提供 sim/synth；第二周新增 structures 模块边界实验，不改 v0 功能逻辑。
"""
from pathlib import Path
import argparse
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def run(command, log):
    """执行工具并原样保留 stdout/stderr；非零退出立即传播，禁止假装通过。"""
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding='utf-8', errors='replace')
    (ROOT / log).write_text(result.stdout, encoding='utf-8')
    print(result.stdout)
    if result.returncode:
        raise SystemExit(result.returncode)
    return result.stdout

def tool(name):
    """接受 PATH 工具名或用户提供的路径；错误指出真实缺项而不静默跳过。"""
    path = shutil.which(name)
    if not path:
        raise SystemExit(f'工具不可用：{name}。先检查安装目录和 PATH。')
    return str(Path(path).resolve())

def main():
    parser = argparse.ArgumentParser(description='DFT Lab v0 实验入口')
    parser.add_argument('action', choices=['sim','structures','synth'])
    parser.add_argument('--iverilog', default='iverilog')
    parser.add_argument('--vvp', default='vvp')
    parser.add_argument('--yosys', default='yosys')
    args = parser.parse_args()
    for directory in ['build/v0','netlist/v0','reports']:
        (ROOT / directory).mkdir(parents=True, exist_ok=True)
    if args.action in ['sim','structures']:
        # 单独指定顶层，避免多个模块意外被当成独立仿真根。
        rtl = [str(p.relative_to(ROOT)) for p in sorted((ROOT/'rtl/v0').glob('*.sv'))]
        # 两个平台共享编译/退出码处理，但结构实验不混入完整事务参考模型。
        name = 'functional' if args.action == 'sim' else 'structures'
        compile_log = 'reports/compile.log' if name == 'functional' else 'reports/structures_compile.log'
        run([tool(args.iverilog), '-g2012', '-s', name+'_tb', '-o',
             f'build/v0/{name}.vvp', *rtl, f'tb/{name}_tb.sv'], compile_log)
        output = run([tool(args.vvp), f'build/v0/{name}.vvp'], f'reports/{name}.log')
        if f'PASS {name.upper()}_V0' not in output:
            raise SystemExit('仿真未执行到最终验收标记。')
    else:
        run([tool(args.yosys), '-s', 'scripts/synth_v0.ys'], 'reports/synth.log')
        run([sys.executable, 'scripts/inspect_netlist.py'], 'reports/inspect.log')

if __name__ == '__main__':
    main()
