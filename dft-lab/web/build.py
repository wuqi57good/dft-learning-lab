"""把当前教学工程变成一个可双击的离线 HTML。

输入：assets 页面源、docs 文件档案、真实源码与 reports；输出 dft_course.html。
只读工程证据，不在网页构建时执行 EDA，也不填造通过数据。
源码字符串作为 JSON 嵌入，转义 </，避免源码内容意外结束 script 标签。
重建后原先已打开的 HTML 需要刷新；学习记录保存在当前浏览器。
"""
from pathlib import Path
import hashlib
import html
import importlib.util
import json
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT/'web'
ASSETS = WEB/'assets'
snapshot_spec = importlib.util.spec_from_file_location('validation_pipeline', ROOT/'scripts/run_all.py')
validation_pipeline = importlib.util.module_from_spec(snapshot_spec)
snapshot_spec.loader.exec_module(validation_pipeline)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify_snapshot(root, hashes, artifacts=False):
    """比对原始字节和完整文件集合；新增文件也必须先经过本轮验收。"""
    label = '生成物' if artifacts else '源码'
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError('完整验收报告缺少'+label+'哈希快照；请重跑 scripts/run_all.py')
    for relative, expected in hashes.items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('验收快照必须使用工程内相对路径：'+relative)
        source = root/path
        if not source.is_file():
            raise ValueError('已验'+label+'文件缺失：'+relative+'；请恢复文件并重跑 scripts/run_all.py')
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(label+'已改变，旧 PASS 已过期：'+relative+'；请重跑 scripts/run_all.py')
    current = validation_pipeline.snapshot_paths(root, artifacts)
    if set(current) != set(hashes):
        raise ValueError(label+'文件集合已改变，旧 PASS 已过期；请重跑 scripts/run_all.py')


def verify_evidence(root, evidence):
    """构建前确认 PASS 对应当前已验源文件、生成物和通过的必要子报告。

    run_all.py 保存原始文件字节的 SHA-256。源码一旦修改，旧 PASS 只能作为
    历史记录，必须重新运行流水线后才能发布新的通过版页面。这里不执行 EDA，
    也不把哈希当作数字签名；检查的是当前文件与本地验收快照的一致性。
    """
    full = evidence['validation-full.json']
    if full.get('status') != 'PASS':
        raise ValueError('完整工程尚未通过，不能构建最终通过版网页；请重跑 scripts/run_all.py')
    verify_snapshot(root, full.get('source_sha256'))
    # 总报告和子报告都要通过，避免单独重跑某一步失败后仍借用旧的总 PASS。
    for name in ['scan/validation.json', 'atpg/scan_replay.json']:
        if evidence[name].get('status') != 'PASS':
            raise ValueError('必要子报告未通过：'+name+'；请重跑 scripts/run_all.py')
    for name in ['drc/v1.json', 'drc/v2.json']:
        if evidence[name].get('pass') is not True:
            raise ValueError('必要 DRC 报告未通过：'+name+'；请重跑 scripts/run_all.py')
    verify_snapshot(root, full.get('artifact_sha256'), artifacts=True)


def generated_card(path):
    """生成物与网页文件用清晰的类别契约；硬件/算法源必须有逐文件人工档案。"""
    if path.startswith('netlist/'):
        purpose = '保存 '+path+' 的完整门级连接，供仿真和逐位追踪；可由综合/扫描插入重新生成。'
        layout = ['生成来源与顶层端口', '网络声明与别名', '组合门及状态单元连接']
        boundary = '不手改生成物；功能变化修改 RTL，测试结构变化修改 scan_insert.py，再重跑流水线。'
        deps = ['scripts/synth_v0.ys', 'dft_tools/scan_insert.py', 'reports/scan_chains.json']
    elif path.startswith('web/'):
        purpose = '提供 '+path+' 对应的课程展示或构建逻辑；最终合并为无网络依赖的单个 HTML。'
        layout = ['课程数据或样式定义', '页面布局/交互实现', '渲染或事件绑定']
        boundary = '只展示教学模型与报告；不能在浏览器里伪造硬件验证通过。'
        deps = ['web/build.py', 'docs/file_cards.json', 'reports/validation-full.json']
    elif path.startswith('docs/'):
        purpose = '保存 '+path+' 的工程解释与审读依据，帮助从结果追到代码、协议和知识来源。'
        layout = ['范围与目标', '分阶段解释及对照', '验证依据与限制']
        boundary = '不把文字声明当工具输出；实测数字以 reports 为准。'
        deps = ['README.md', 'reports/validation-full.json']
    elif path.startswith('patterns/'):
        purpose = '保存 '+path+' 的算法生成检测向量，明确输入顺序并供 HDL 回放。'
        layout = ['输入或链顺序', '向量数据', '故障/输出约定']
        boundary = '不手填成功向量；由 run_atpg.py 从当前网表重新生成。'
        deps = ['scripts/run_atpg.py', 'reports/scan_chains.json']
    else:
        raise ValueError('缺少独立工程档案：'+path)
    return {'purpose': purpose, 'layout': layout, 'boundary': boundary, 'dependencies': deps,
            'scale': '实际行数由当前文件计算。此文件保持一个可独立重建或审读的职责，生成数据不按行数硬拆。',
            'decision': '源文件、生成物与展示分层，保留可追溯输入。',
            'alternate': '把内容复制到各处会造成修改后版本不一致；这里在构建时从当前工程统一读取。',
            'failure': '若脱离来源手改，页面、网表和真实运行记录会不一致，必须重建并核对。'}


def main():
    cards = {}
    for name in ['cards_baseline.json', 'cards_scan.json', 'cards_atpg.json', 'cards_integration.json', 'cards_build.json']:
        cards.update(read_json(ROOT/'docs'/name))
    sources = []
    for directory in ['rtl', 'tb', 'scripts', 'dft_tools', 'constraints', 'docs', 'web', 'netlist', 'patterns', 'tests']:
        for path in sorted((ROOT/directory).rglob('*')):
            relative = path.relative_to(ROOT).as_posix()
            if path.is_file() and path.suffix in {'.sv','.svh','.py','.ys','.sdc','.md','.js','.css','.html','.v','.ps1'} and '__pycache__' not in path.parts and path.name != 'dft_course.html':
                sources.append(relative)
    sources += ['README.md', 'Makefile', 'run.ps1']
    files = {p: (ROOT/p).read_text(encoding='utf-8-sig') for p in sorted(set(sources))}
    complete_cards = {}
    for path, source in files.items():
        card = dict(cards[path]) if path in cards else generated_card(path)
        card['path'] = path
        card['lines'] = len(source.splitlines())
        card.setdefault('scale', '保持单一职责，不以目标行数拆分或填充实现。')
        match = re.search(r'/(v[012])/', path)
        card.setdefault('version', match[1] if match else 'v3 · 全流程' if path.startswith(('dft_tools/','scripts/run_','web/')) else '课程资料')
        for key in ['purpose','layout','boundary','dependencies','decision','alternate','failure']:
            if not card.get(key): raise ValueError(f'{path} 档案缺少 {key}')
        complete_cards[path] = card
    evidence = {}
    for path in sorted((ROOT/'reports').rglob('*.json')):
        evidence[path.relative_to(ROOT/'reports').as_posix()] = read_json(path)
    required = ['drc/inventory.json','drc/v0.json','drc/v1.json','drc/v2.json',
                'scan_chains.json','scan/validation.json','scan/lockup_wave.json','atpg/summary.json',
                'atpg/scan_replay.json','coverage/coverage.json','timing/cost_timing.json','validation-full.json']
    for key in required:
        if key not in evidence: raise FileNotFoundError('缺少实际报告：'+key)
    verify_evidence(ROOT, evidence)
    data = {'files':files,'cards':complete_cards,'week2':read_json(ROOT/'reports/week2.json'),'evidence':evidence}
    css_names=['course.css','polish.css','week2.css','weeks3-7.css','advanced.css','learning.css']
    css='\n'.join((ASSETS/n).read_text(encoding='utf-8-sig') for n in css_names)
    js='\n'.join((ASSETS/n).read_text(encoding='utf-8-sig') for n in ['course-main.js','course-extra.js','week2.js','advanced.js','learning.js'])
    template=(ASSETS/'course.template.html').read_text(encoding='utf-8')
    template=template.replace('__WEEK2__',(ASSETS/'week2.html').read_text(encoding='utf-8'))
    template=template.replace('__WEEKS_REMAINING__',(ASSETS/'weeks3-7.html').read_text(encoding='utf-8'))
    log=(ROOT/'reports/functional.log').read_text(encoding='utf-8')
    values={'CSS':css,'JS':js,'DATA':json.dumps(data,ensure_ascii=False).replace('</','<\\/'),
            'CELL_TOTAL':str(evidence['netlist_inventory.json']['generic_cell_total']),
            'SOURCE_COUNT':str(len(files)),
            'SIM_LOG':html.escape('\n'.join(l for l in log.splitlines() if l.startswith('PASS')))}
    # 只替换模板本身的一遍。源码可能也含同名占位符，不能递归替换而破坏内嵌JSON。
    document=re.sub(r'__(CSS|JS|DATA|CELL_TOTAL|SOURCE_COUNT|SIM_LOG)__',lambda m:values[m[1]],template)
    # 模板占位符只检查模板本体；源码里允许包含 build.py 的占位符字符串。
    if re.search(r'__(?:CSS|JS|DATA|WEEK2|WEEKS_REMAINING|SOURCE_COUNT|CELL_TOTAL|SIM_LOG)__', template.replace('__CSS__','').replace('__JS__','').replace('__DATA__','').replace('__CELL_TOTAL__','').replace('__SOURCE_COUNT__','').replace('__SIM_LOG__','')):
        raise ValueError('仍有未替换的章节占位符')
    (ROOT/'docs/file_cards.json').write_text(json.dumps(complete_cards,ensure_ascii=False,indent=2),encoding='utf-8')
    (WEB/'dft_course.html').write_text(document,encoding='utf-8')
    print(f'PASS WEB_BUILD files={len(files)} bytes={len(document.encode("utf-8"))}')


if __name__ == '__main__':
    main()
