# DFT Lab · 七周扫描链与 ATPG 课程

**[在线阅读](https://wuqi57good.github.io/dft-learning-lab/)** · **[下载完整工程](https://wuqi57good.github.io/dft-learning-lab/downloads/dft-lab-complete.zip)**

面向会编程的 DFT 初学者，从 RTL、真实网表、扫描链到 ATPG 向量回放。网页沿用暖米白、陶土与鼠尾草绿配色，支持手机阅读、课程/代码搜索、逐行解释、笔记和学习进度备份。无需账号即可阅读，学习记录保存在自己的浏览器中。

## 仓库内容

| 路径 | 用途 |
|---|---|
| `index.html` | GitHub Pages 首页；源码和课程数据内嵌，无 CDN 或外部字体依赖 |
| `dft-lab/` | 完整可复现工程：RTL、Python 工具、TB、测试、约束、生成网表、报告、VCD 与网页源码 |
| `downloads/dft-lab-complete.zip` | 已核验的完整工程下载包 |
| `交付说明.md` | 实现范围、验收结果与知识边界 |
| `SHA256SUMS.txt` | 首页及下载包的 SHA-256 校验值 |

直接下载 ZIP、解压并双击 `dft-lab/web/dft_course.html` 也可离线学习。完整源码可在仓库中浏览，工具安装与逐周命令见 [工程 README](dft-lab/README.md)。原始问题文档、本机工具、编译缓存和个人学习笔记未加入仓库。

## 课程与已验结果

- 七周课程、78 个内嵌源码/资料文件、交互实验、24 道自测题与实操。
- 293 个 FF；v1 单链；v2 四链长度为 74/73/73/73，含 4 个 Lock-up。
- 局部组合锥的 22 个 stem stuck-at 故障：19 可测，3 个在该观察边界下不可测。
- 19 个可测故障全部经过真实完整 DUT 的扫描装载、Capture 与 SO 卸载，累计 11,134 次 SO 位比较。
- 13 项完整流程、39 项标准库回归以及桌面/手机浏览器检查通过。

**19/22 = 86.36% 是局部锥故障覆盖率，不是全芯片覆盖率。** 未执行工艺库面积映射、物理 STA、SDF 或布局布线；教学预算不能替代签核。算法是明确限定门集的简化 D-cube 搜索。具体证据见 [完整验收报告](dft-lab/reports/validation-full.json) 与 [来源说明](dft-lab/docs/sources.md)。

## 复现工程

安装 Python 3、Icarus Verilog 和 Yosys 后：

```sh
cd dft-lab
python scripts/run_all.py
python web/build.py
```

YoWASP 可使用 `python scripts/run_all.py --yosys yowasp-yosys`。工具不在 PATH 时传 `--iverilog`、`--vvp`、`--yosys` 完整路径。浏览器测试需要另外安装 Playwright，命令见工程 README。

仓库通过 `.gitattributes` 保留原始文件字节，以维持报告中的哈希可复核性。不要手改生成报告来绕过验收；修改 RTL 或工具后重新运行完整流程。

## 发布方式

GitHub Pages 从 `main` 分支根目录发布，`.nojekyll` 使站点作为静态文件提供。站点不需要后端或构建服务。更新课程时，应先重跑工程检查，再将新的离线网页复制为根目录 `index.html`，更新工程目录与下载 ZIP，并重新计算 `SHA256SUMS.txt`。

本地文件与 HTTPS 网站使用不同的浏览器存储空间。迁移学习进度时，先在原页面导出学习记录，再在在线页面导入。
