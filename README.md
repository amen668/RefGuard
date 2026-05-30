# RefGuard

RefGuard 是一个面向学术参考文献的开源核验工具，用于检查 BibTeX 条目是否能被公开学术元数据源支持。

项目关注“参考文献身份核验”：题名、作者、年份、DOI、arXiv ID 与来源证据。当前方法不使用 LLM。

## 功能

- 基于 Crossref、OpenAlex、arXiv、DBLP、Semantic Scholar 核验 BibTeX 参考文献。
- 将多数据源候选证据融合为匹配概率和明确状态。
- 检测重复参考文献条目。
- 对 LaTeX 项目检查 BibTeX 条目使用情况。
- 输出 JSON 与 Markdown 报告。
- 支持命令行工具和 FastAPI 服务。

## 不做什么

- 默认只接入公开、可文档化的学术元数据源。
- 不抓取 Google Scholar。
- 不使用 LLM 判断参考文献是否真实存在。
- 不包含用户上传论文或私人项目数据。

## 合规与职业边界

RefGuard 是个人研究与开源项目，不代表作者任职机构、任何数据平台或商业服务。本项目不使用雇主资源、内部资料、非公开数据、账号凭据或工作产出。

项目代码只面向公开可访问的学术元数据接口和公开书目信息。公开可访问不等于自动可再分发；用于论文附件、公开 release 或第三方复用前，应逐项核查数据来源、许可、API 条款和引用要求。

详见 [DISCLAIMER.md](DISCLAIMER.md)。

## 安装

```bash
pip install -e .
```

开发环境：

```bash
pip install -e ".[dev]"
```

## 命令行用法

核验 BibTeX 文件：

```bash
refguard verify bib --input tests/test_bib.bib --profile balanced --out ./report
```

兼容旧命令名：

```bash
refcheck verify bib --input tests/test_bib.bib
```

核验 BibTeX 并检查 LaTeX 引用使用情况：

```bash
refguard verify project --bib paper/references.bib --tex paper/main.tex --check-usage on --out ./report
```

## API 用法

启动 API 服务：

```bash
uvicorn main:app --reload
```

打开：

- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/api/v1/sources/status

请求示例：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/verify/bib" \
  -H "Content-Type: application/json" \
  -d '{"bibtex_content":"@article{demo,title={Attention Is All You Need},author={Vaswani, Ashish and Shazeer, Noam},year={2017}}","profile":"balanced"}'
```

## 配置

只有需要本地覆盖配置时，才将 `.env.example` 复制为 `.env`。

所有 API key 都是可选项，仅用于公开元数据源的访问限额，不应提交到版本库：

- `SEMANTIC_SCHOLAR_API_KEY`：可选，用于提高请求限额。
- `OPENALEX_API_KEY`：可选。
- `CROSSREF_MAILTO`：可选，用于 Crossref polite pool。

## 实验数据

`data/refguard_input.jsonl` 是当前基准数据，共 1295 条参考文献记录，其中真实文献 1087 条、幻觉文献 208 条。`data/sample_refguard_input.jsonl` 是 20 条小样例，便于快速查看字段结构。

当前项目数据来自公开来源和公开元数据。请将其视为研究数据：只保留书目信息、标签与来源说明。不要提交论文全文、用户上传文件、非公开数据源导出、API key 或 cookie。正式公开完整数据集前，请单独附数据说明和许可核查结果。

运行基准测试辅助脚本。输出目录默认为 `eval_report/`，该目录是生成产物，不纳入版本库：

```bash
python eval/run_benchmark.py --input data/refguard_input.jsonl --out eval_report
```

## 开发检查

```bash
python -m pytest tests -q
python -m compileall -q refguard eval
refguard --help
```

## 许可证

代码采用 MIT License 发布，详见 [LICENSE](LICENSE)。
