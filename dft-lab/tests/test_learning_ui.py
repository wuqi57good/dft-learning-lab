"""独立浏览器回归：python tests/test_learning_ui.py [--browser 浏览器路径]。

需要 Playwright 和 Chromium 或兼容浏览器；使用临时会话，不读取个人浏览器资料。
本脚本不属于 EDA 主流程，不以网页通过替代硬件检查。
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import traceback
import uuid


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/validation-learning-ui.json"


def snapshot(page):
    """失败导入必须保持所有学习状态；状态提示本身可以改变。"""
    return page.evaluate("""() => ({
      checks: Array.from(document.querySelectorAll('[data-check],[data-stage-check]'))
        .map(c => [c.dataset.check, c.checked]),
      notes: document.querySelector('#learning-notes').value,
      week2Notes: document.querySelector('#w2-notes').value,
      storage: Object.fromEntries(Object.keys(localStorage).sort().map(k => [k, localStorage.getItem(k)]))
    })""")


def search(page, query, scope="全部"):
    if not page.locator("#learning-search-dialog").is_visible():
        page.keyboard.press("Control+k")
    page.locator("#learning-search-scope").select_option(scope)
    page.locator("#learning-search-input").fill(query)
    return page.locator("[data-learning-result]")


def import_record(page, value, valid=True, raw=False):
    # 每次等待 input 清空，避免异步 File.text() 尚未完成便读取状态。
    content = value if raw else json.dumps(value, ensure_ascii=False)
    page.locator("#import-learning-record").set_input_files({
        "name": "learning.json", "mimeType": "application/json",
        "buffer": content.encode("utf-8"),
    })
    page.wait_for_function("document.querySelector('#import-learning-record').value === ''")
    status = page.locator("#learning-record-status").inner_text()
    assert status.startswith("已合并学习记录：" if valid else "未导入："), status


def run_checks(page, checks):
    from playwright.sync_api import expect

    page.evaluate("document.documentElement.style.scrollBehavior='auto'")
    opener = page.locator("#open-learning-search")
    opener.click()
    expect(page.locator("#learning-search-input")).to_be_focused()
    assert page.locator("[data-learning-result]").count() == 0

    results = search(page, "reset_value negative", "代码")
    lower = results.locator("b").all_text_contents()
    assert "rtl/v1/scan_dff.sv" in lower
    assert set(results.locator("small").all_text_contents()) == {"代码"}
    upper = search(page, "RESET_VALUE NEGATIVE", "代码").locator("b").all_text_contents()
    assert upper == lower, "大小写改变了搜索结果"
    search(page, "Q <= SI;", "代码")
    assert "rtl/v1/scan_dff.sv" in results.locator("b").all_text_contents()
    search(page, "notfound_" + uuid.uuid4().hex)
    assert results.count() == 0
    assert "没有匹配结果" in page.locator("#learning-search-count").inner_text()
    search(page, "<img", "代码")
    assert results.count() > 0, "测试源码中的特殊字符必须能被搜到"
    assert results.locator("img,script,iframe").count() == 0
    checks["search_filters_and_escaping"] = "PASS: 多词、大小写、范围、空结果、特殊字符"

    search(page, "scan", "代码")
    assert results.count() >= 2
    page.locator("#learning-search-input").press("ArrowDown")
    expect(results.nth(0)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(results.nth(1)).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(results.nth(0)).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#learning-search-dialog")).not_to_be_visible()
    expect(opener).to_be_focused()
    page.keyboard.press("Control+k")
    expect(page.locator("#learning-search-input")).to_be_focused()
    page.locator("#close-learning-search").click()
    expect(opener).to_be_focused()
    checks["keyboard_and_close_focus"] = "PASS: Ctrl+K、上下箭头、Escape、关闭后恢复焦点"

    path = "rtl/v1/scan_dff.sv"
    source = (ROOT / path).read_text(encoding="utf-8-sig")
    expected_line = next(i for i, line in enumerate(source.splitlines(), 1) if "RESET_VALUE" in line)
    result = search(page, "RESET_VALUE NEGATIVE", "代码").filter(has=page.get_by_text(path, exact=True))
    result.click()
    expect(page.locator("#learning-search-dialog")).not_to_be_visible()
    assert page.locator("#file-path").inner_text() == path
    row = page.locator(f'#code-lines [data-line="{expected_line}"]')
    expect(row).to_be_focused()
    assert "selected" in row.get_attribute("class")
    assert f"第 {expected_line} 行" in page.locator("#line-explain").inner_text()
    assert "RESET_VALUE" in row.inner_text()
    checks["source_navigation"] = f"PASS: {path}:{expected_line} 与磁盘源码独立核对并保留焦点"

    course_title = "冗余：没有解，也是一种结论"
    results = search(page, "冗余 结论", "课程")
    assert set(results.locator("small").all_text_contents()) == {"课程"}
    results.filter(has=page.get_by_text(course_title, exact=True)).click()
    expect(page.get_by_role("heading", name=course_title, exact=True)).to_be_focused()
    detail = page.locator(".lesson details").filter(has_text="Tapeout 许可").first
    assert detail.count() == 1
    detail.evaluate("node => node.open = false")
    search(page, "Tapeout 许可", "课程").first.click()
    assert detail.evaluate("node => node.open"), "命中的折叠答案仍被隐藏"
    exam = page.locator(".final-exam details").first
    exam.evaluate("node => node.open = false")
    title = exam.locator("summary").inner_text()
    search(page, title, "课程")
    page.locator("#learning-search-input").press("Enter")
    assert exam.evaluate("node => node.open")
    expect(exam.locator("summary")).to_be_focused()
    checks["course_navigation"] = "PASS: 课程标题、多词正文、折叠答案、Enter 定位与焦点"

    page.locator("#learning-record > summary").click()
    checkbox = page.locator("[data-check],[data-stage-check]")
    assert checkbox.count() >= 3
    checkbox.nth(0).check()
    checkbox.nth(1).uncheck()
    checkbox.nth(2).uncheck()
    first_key = checkbox.nth(0).get_attribute("data-check")
    second_key = checkbox.nth(1).get_attribute("data-check")
    third_key = checkbox.nth(2).get_attribute("data-check")
    page.locator("#learning-notes").fill("已有工程笔记")
    page.locator("#w2-notes").fill("已有第二周笔记")
    before = snapshot(page)
    with page.expect_download() as pending:
        page.locator("#export-learning-record").click()
    downloaded = pending.value
    assert downloaded.suggested_filename == "DFT-学习记录.json"
    exported = json.loads(Path(downloaded.path()).read_text(encoding="utf-8"))
    assert exported["schema"] == "dft-lab.learning.v1"
    assert exported["checks"] == dict(before["checks"])
    assert exported["notes"] == before["notes"]
    assert exported["week2Notes"] == before["week2Notes"]
    datetime.fromisoformat(exported["exportedAt"].replace("Z", "+00:00"))
    incoming = dict(exported, checks={first_key: False, second_key: True, "unknown-check": True},
                    notes="另一设备的补充", week2Notes="第二周的补充")
    import_record(page, incoming)
    merged = snapshot(page)
    assert dict(merged["checks"])[first_key] is True
    assert dict(merged["checks"])[second_key] is True
    assert len(merged["checks"]) == len(before["checks"])
    for key in ("notes", "week2Notes"):
        assert before[key] in merged[key] and incoming[key] in merged[key]
    import_record(page, incoming)
    assert snapshot(page) == merged, "重复导入产生了重复数据"
    import_record(page, dict(incoming, notes="  ", week2Notes=""))
    assert snapshot(page) == merged, "空笔记覆盖了原记录"
    checks["record_export_and_merge"] = "PASS: 导出、只合并 true、保留两处笔记、未知项忽略、重复导入去重"

    invalid = [
        None, [], {}, dict(incoming, schema="unknown"),
        dict(incoming, checks=None), dict(incoming, checks=[]),
        dict(incoming, checks={third_key: True, "bad": "true"}),
        dict(incoming, checks={second_key: 1}),
        dict(incoming, notes=123), dict(incoming, week2Notes={}),
    ]
    import_record(page, "{ invalid JSON", valid=False, raw=True)
    assert snapshot(page) == merged
    for value in invalid:
        import_record(page, value, valid=False)
        assert snapshot(page) == merged, f"失败导入改变了状态：{value!r}"
    checks["invalid_import_atomicity"] = f"PASS: {len(invalid) + 1} 种无效 JSON/字段均无状态改变"

    payload = '<img src="https://invalid.example/learning-test" onerror="window.__learningInjected=1">'
    import_record(page, dict(incoming, notes=payload, week2Notes=payload))
    assert payload in page.locator("#learning-notes").input_value()
    assert payload in page.locator("#w2-notes").input_value()
    assert page.evaluate("typeof window.__learningInjected") == "undefined"
    assert page.locator('img[src*="learning-test"]').count() == 0
    stored = snapshot(page)
    page.reload()
    assert snapshot(page) == stored, "重新打开页面后学习记录未保留"
    checks["plain_text_and_persistence"] = "PASS: HTML 仅作为文字，刷新后进度与笔记保留"

    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate("window.scrollTo(0,0)")
    page.locator("#mobile-learning-search").click()
    search(page, "scan", "代码")
    assert page.locator("[data-learning-result]").count() > 0
    box = page.locator("#learning-search-dialog").bounding_box()
    assert box and box["x"] >= 0 and box["y"] >= 0
    assert box["x"] + box["width"] <= 391 and box["y"] + box["height"] <= 845
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    assert page.locator("#learning-search-dialog").evaluate("d => d.scrollWidth <= d.clientWidth + 1")
    page.locator("#close-learning-search").click()
    expect(page.locator("#mobile-learning-search")).to_be_focused()
    page.locator("#learning-record").evaluate("node => node.open = true")
    page.locator("#learning-notes").scroll_into_view_if_needed()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    checks["mobile_layout"] = "PASS: 390×844 弹窗完整可见、无页面横向溢出、关闭后焦点正确"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Chromium/Edge/Chrome 可执行文件；默认使用 Playwright Chromium")
    parser.add_argument("--html", type=Path, default=ROOT / "web/dft_course.html", help="待验收的离线 HTML")
    args = parser.parse_args()
    report = {"status": "FAIL", "checked_at": datetime.now(timezone.utc).isoformat(), "checks": {}}
    errors, external = [], []
    try:
        from playwright.sync_api import sync_playwright
        html = args.html.resolve()
        report["tested_html"] = html.relative_to(ROOT).as_posix() if html.is_relative_to(ROOT) else html.name
        # 报告会内嵌回 HTML；记录构建来源，避免哈希包含自身的循环。
        ui_sources = [ROOT / "web/build.py", *sorted((ROOT / "web/assets").rglob("*"))]
        report["ui_source_sha256"] = {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in ui_sources if path.is_file()
        }
        with sync_playwright() as p:
            options = {"headless": True}
            if args.browser:
                options["executable_path"] = args.browser
            browser = p.chromium.launch(**options)
            try:
                context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
                page = context.new_page()
                page.set_default_timeout(10000)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda req: external.append(req.url) if req.url.startswith(("https://", "http://")) else None)
                context.route("http://**/*", lambda route: route.abort())
                context.route("https://**/*", lambda route: route.abort())
                page.goto(html.as_uri())
                run_checks(page, report["checks"])
                assert not errors, errors
                assert not external, external
                report["checks"]["offline_and_javascript"] = "PASS: 无外部网络请求，无 JavaScript 异常"
                report["status"] = "PASS"
            finally:
                browser.close()
    except Exception as error:
        report["failure"] = f"{type(error).__name__}: {error}"
        report["traceback"] = traceback.format_exc()
    report["javascript_errors"] = errors
    report["external_network_requests"] = external
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"{report['status']} LEARNING_UI")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
