"""离线课程的真实浏览器回归，输出 reports/validation-web.json。

先安装 Playwright 及 Chromium；也可用 --browser 指向已安装的 Chromium 系浏览器。
--html 指定待验 HTML；--screenshots 可选保存桌面、课程与手机截图的目录。
默认验收工程内 web/dft_course.html；源码、报告与硬件哈希逐项核对。
本测试只验收网页呈现与交互，不代替硬件仿真或制造签核。
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify_page(page, html_path, checks, screenshots, previous_report):
    errors, requests = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    page.goto(html_path.as_uri())
    page.evaluate("document.documentElement.style.scrollBehavior='auto'")
    assert not errors, errors
    data = page.evaluate('DATA')
    for name, source in data['files'].items():
        assert source == (ROOT/name).read_text(encoding='utf-8-sig'), name
        assert data['cards'][name]['lines'] == len(source.splitlines()), name
        for key in ['purpose', 'layout', 'scale', 'boundary', 'dependencies', 'decision', 'alternate', 'failure', 'version']:
            assert data['cards'][name].get(key), (name, key)
    checks['source_files'] = len(data['files'])
    checks['source_identity'] = 'PASS: all embedded sources, engineering cards and line counts match'
    for name, evidence in data['evidence'].items():
        # 当前网页报告运行中必须失效；页面里的上一轮报告与启动前快照核对。
        expected = previous_report if name == 'validation-web.json' else json.loads((ROOT/'reports'/name).read_text(encoding='utf-8'))
        assert evidence == expected, name
    for name, digest in data['evidence']['validation-full.json']['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
    checks['evidence_identity'] = 'PASS: all reports and verified source hashes match'
    assert page.evaluate("Array.from(document.querySelectorAll('section[id]')).filter(e=>/^week[3-7]$/.test(e.id)).map(e=>e.id)") == ['week3', 'week4', 'week5', 'week6', 'week7']
    assert not page.evaluate("Array.from(document.querySelectorAll('[id]')).map(e=>e.id).filter((x,i,a)=>a.indexOf(x)!==i)")
    assert not page.evaluate("Array.from(document.querySelectorAll('a[href^=\"#\"]')).filter(a=>!document.getElementById(a.getAttribute('href').slice(1))).map(a=>a.outerHTML)")
    checks['chapters_and_anchors'] = 'PASS'

    def snapshot(name):
        if screenshots:
            page.screenshot(path=str(screenshots/name))

    snapshot('desktop.png')
    # 原有五个实验继续工作，后续教学内容不能破坏前两周。
    for expected in ['1000', '0100', '1010', '1101', '0101', '0010', '0001', '0000', '0000']:
        page.locator('#scan-next').click()
        assert page.locator('#scan-state').inner_text() == expected
    assert page.locator('#scan-out').inner_text() == '1010'
    page.locator('#scan-reset').click()
    assert page.locator('#scan-state').inner_text() == '0000'
    page.locator('#tree-next').click()
    assert '2 步' in page.locator('#tree-note').inner_text()
    page.locator('#tree-reset').click()
    page.locator('#fault-type').select_option('1')
    page.locator('#fault-capture').click()
    assert '未采样' not in page.locator('#fault-obs').inner_text()
    page.locator('#skew').fill('1.5')
    page.locator('#skew').dispatch_event('input')
    assert page.locator('#hold-raw').inner_text().startswith('-')
    page.locator('#coverage-range').fill('16')
    page.locator('#coverage-range').dispatch_event('input')
    assert '16 / 16' in page.locator('#pattern-count').inner_text()
    checks['original_five_labs'] = 'PASS'

    # 真实链映射、各链末位、搜索与正确/错误 Lock-up VCD 的分歧。
    for version, lengths in [('v1', [293]), ('v2', [74, 73, 73, 73])]:
        for index, length in enumerate(lengths):
            page.locator(f'#{version}-chain-select').select_option(str(index))
            assert page.locator(f'#{version}-chain-cells button').count() == length
            page.locator(f'#{version}-chain-cells button').last.click()
            assert f'第 {length-1} 位' in page.locator(f'#{version}-chain-detail').inner_text()
        page.locator(f'#{version}-chain-search').fill('missing_state_no_match')
        assert page.locator(f'#{version}-chain-cells button').count() == 0
        page.locator(f'#{version}-chain-search').fill('')
    for _ in range(4):
        page.locator('#lock-real-next').click()
    assert page.locator('#lock-real-time').inner_text() == '669 ns'
    assert page.locator('#lock-real-readout .proof-card b').all_text_contents() == ['0', '1']
    page.locator('#lock-real-reset').click()
    assert page.locator('#lock-real-time').inner_text() == '664 ns'
    checks['real_scan_and_lockup'] = 'PASS: five chains and actual 669 ns divergence'
    while not page.locator('#actual-next').is_disabled():
        page.locator('#actual-next').click()
    assert page.locator('#actual-tree .conflict').count() > 0
    assert page.locator('#actual-tree .success').count() > 0
    replay = data['evidence']['atpg/scan_replay.json']
    assert replay['status'] == 'PASS' and len(replay['cases']) == replay['detected_replayed_count'] == 19
    assert len({case['fault'] for case in replay['cases']}) == 19
    assert replay['total_compared_so_bits'] == 19 * 293 * 2
    assert set(replay['skipped_proven_untestable']) == {'e/SA0', 'e/SA1', 'r/SA0'}
    page.locator('#full-replay-panel details summary').click()
    rows = page.locator('#full-replay-panel details table tbody tr')
    assert rows.count() == 19
    for index, case in enumerate(replay['cases']):
        expected = [case['fault'], ' '.join(str(case['pattern'][k]) for k in data['evidence']['atpg/summary.json']['input_order']), case['observation'], f"{case['observation_chain']} / {case['observation_shift_cycle_zero_based']}", f"{case['good_bit']} / {case['bad_bit']}", 'PASS']
        assert rows.nth(index).locator('td').all_text_contents() == expected, case['fault']
    assert page.locator('#full-replay-panel > .table-scroll tbody tr').count() == 3
    page.locator('#actual-fault').select_option('r/SA0')
    assert '没有检测向量' in page.locator('#actual-pattern').inner_text()
    assert '不可测，没有可计入的检测回放' in page.locator('#replay-selected').inner_text()
    page.locator('#actual-fault').select_option('q/SA1')
    assert '正常 0 / 故障 1' in page.locator('#replay-selected').inner_text()
    page.locator('#actual-coverage-range').fill('7')
    page.locator('#actual-coverage-range').dispatch_event('input')
    assert '19/22 = 86.36%' in page.locator('#actual-coverage-note').inner_text()
    page.locator('#actual-coverage-reset').click()
    assert '0/22 = 0.00%' in page.locator('#actual-coverage-note').inner_text()
    checks['real_atpg_and_coverage'] = 'PASS: 19 replay rows, untestable boundary, backtracking and fixed denominator'
    hold_before = page.locator('#budget-results .proof-card b').nth(1).inner_text()
    page.locator('#budget-period').fill('20')
    page.locator('#budget-period').dispatch_event('input')
    assert page.locator('#budget-results .proof-card b').nth(1).inner_text() == hold_before
    page.locator('#reorder-toggle').check()
    assert '长度 12' in page.locator('#reorder-note').inner_text()
    checks['timing_and_reordering'] = 'PASS'

    for name in ['rtl/v0/dft_demo_top.sv', 'rtl/v1/scan_dff.sv', 'rtl/v2/lockup_latch.sv', 'dft_tools/atpg.py', 'dft_tools/scan_insert.py', 'scripts/run_all.py', 'constraints/v2.sdc', 'netlist/v2/design.v', 'README.md']:
        page.evaluate('(path)=>openFile(path)', name)
        assert page.locator('#file-path').inner_text() == name
        assert page.locator('#file-stage').inner_text()
        page.locator('#code-lines .code-line').nth(2).click()
        assert '第 3 行' in page.locator('#line-explain').inner_text()
    with page.expect_download() as download:
        page.locator('#download-file').click()
    assert Path(download.value.path()).read_text(encoding='utf-8') == data['files']['README.md']
    page.locator('#expand-code').click()
    assert 'expanded' in page.locator('#code-scroll').get_attribute('class')
    checks['code_browser'] = 'PASS: source stages, line explanations, expansion and exact download'
    checkboxes = page.locator('[data-check],[data-stage-check]')
    for index in range(checkboxes.count()):
        checkboxes.nth(index).check()
    assert '100%' in page.locator('#progress-caption').inner_text()
    page.reload()
    assert '100%' in page.locator('#progress-caption').inner_text()
    checks['progress'] = 'PASS: seven-week progress and persistence'
    page.evaluate("document.documentElement.style.scrollBehavior='auto'")
    for week in ['week5', 'week6']:
        page.locator('#'+week).scroll_into_view_if_needed()
        snapshot(week+'.png')
    page.set_viewport_size({'width': 390, 'height': 844})
    page.evaluate('window.scrollTo(0,0)')
    snapshot('mobile.png')
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    page.locator('#menu-toggle').click()
    assert 'mobile-open' in page.locator('#sidebar').get_attribute('class')
    page.locator('nav a[href="#week6"]').click()
    assert 'mobile-open' not in (page.locator('#sidebar').get_attribute('class') or '')
    page.locator('#w6-evidence').scroll_into_view_if_needed()
    snapshot('mobile-atpg.png')
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    page.locator('#actual-fault').focus()
    page.keyboard.press('ArrowDown')
    page.keyboard.press('Enter')
    checks['mobile_and_keyboard'] = 'PASS: 390px viewport, menu, scrolling and keyboard selection'
    assert not errors, errors
    external = [url for url in requests if url.startswith(('http://', 'https://'))]
    assert not external, external
    checks['javascript_errors'], checks['external_network_requests'] = errors, external


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', help='Chromium 系浏览器可执行文件；默认使用 Playwright Chromium')
    parser.add_argument('--html', type=Path, default=ROOT/'web/dft_course.html')
    parser.add_argument('--screenshots', type=Path, help='可选截图目录')
    args = parser.parse_args()
    destination = ROOT/'reports/validation-web.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    previous_text = destination.read_text(encoding='utf-8') if destination.exists() else None
    result = {'schema': 'dft-lab.validation.web.v1', 'status': 'RUNNING', 'checks': {}, 'source_sha256': {}}
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        from playwright.sync_api import sync_playwright
        if args.screenshots:
            args.screenshots.mkdir(parents=True, exist_ok=True)
        previous_report = json.loads(previous_text) if previous_text else None
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, **({'executable_path': args.browser} if args.browser else {}))
            verify_page(browser.new_page(viewport={'width': 1440, 'height': 1000}), args.html.resolve(), result['checks'], args.screenshots, previous_report)
            browser.close()
        for path in [ROOT/'web/build.py', *sorted((ROOT/'web/assets').rglob('*'))]:
            if path.is_file():
                result['source_sha256'][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        result['status'] = 'PASS'
    except BaseException as error:
        result['status'], result['error'] = 'FAIL', f'{type(error).__name__}: {error}'
        print(result['error'], file=sys.stderr)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if result['status'] != 'PASS':
        raise SystemExit(1)
    print('PASS WEB_UI_REGRESSION')


if __name__ == '__main__':
    main()
