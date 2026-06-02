# RefGuard 基准数据卡

## 基本信息

`refguard_input.jsonl` 是 RefGuard 的论文实验基准数据，由源数据 `data/citation_dataset_final_v4.json` 通过 `scripts/build_refguard_input.py` 生成。数据文件本身按 `.gitignore` 不入库，由下述脚本可复现重建。

数据仅包含书目信息、核验标签和必要元数据，不包含论文全文、用户上传文件、账号凭据、cookie 或 API 原始响应。

## 实际分布（v4，2537 条）

质量摘要见 `refguard_input_summary.json`；当前版本 `duplicate_ids=0`、`placeholder_urls=0`、所有 `missing.*=0`。

| 维度 | 分布 |
| --- | --- |
| 标签 | real 1937 / hallucination 600（≈3.2:1）|
| 语种 | English 1875 / Chinese 662 |
| 文献类型 | journal 1495 / conference 353 / preprint 248 / book 214 / thesis 122 / technical_report 105 |
| 学科（CLC）| TP 933 / R 397 / O 217 / X 143 / T 142 / F 134 / Q 132 / S 120 / P 106 / K 88 / G 74 / B 50 / N 1 |
| 划分 | test 2037 / dev 500（按 `source_paper` 无泄漏分组）|
| 核验来源 | OpenAlex+doi.org 解析 1937 / GPTZero 100 / 合成负向核验 500 |

**与设计目标（3000）的差距，如实记录：** 真实文献止于 1937（目标 2400），缺口集中在中文——OpenAlex `has_doi:true` 的中文带 DOI 记录在所用 concept 下已基本采尽（中文 662 vs 目标 900）。再上量需接入 Crossref 中文期刊 / DOAJ / PubMed 中文医学等额外公开源。CLC 偏 TP（37%）、N 类仅 1 条，反映各学科公开带 DOI 元数据的密度差异，非采样错误。doc_type 经定向补采后六类齐全，已无「单一期刊」问题。

## 字段说明

每行是一条 JSON 记录，主要字段如下：

- `paper_id`：记录编号。
- `paper_title`：来源论文题名；没有来源论文时为空。
- `paper_url`：来源论文公开 URL；没有时为空。
- `reference.raw`：原始参考文献文本。
- `reference.parsed.title`：参考文献题名。
- `reference.parsed.authors`：作者列表。
- `reference.parsed.year`：发表年份。
- `reference.parsed.venue`：期刊、会议、出版社或其他来源。
- `reference.parsed.doi`：DOI，没有时为 `null`。
- `reference.parsed.arxiv`：arXiv 编号，没有时为 `null`。
- `ground_truth.is_hallucinated`：是否为幻觉文献。
- `ground_truth.label`：原始标签，取值为 `real` 或 `hallucination`。
- `ground_truth.notes`：标注状态和可核验性说明。
- `source`：数据版本标识。
- `meta`：语言、文献类型、学科（中图法 CLC 大类标识，如 `TP`/`R`）、幻觉类型等实验元数据。

源文件 `citation_dataset_final_v4.json` 额外带 `split` 字段（`dev`/`test`），按 `source_paper` 分组划分以避免泄漏；build 脚本不消费该字段。

## 数据来源与采集

源文件由以下脚本生成（分布见 `BIBTEX_DATA_PREPARATION.md`）：

- `scripts/collect_real_refs.py`：按 CLC 大类×语种从 OpenAlex 分层采集真实文献，每条经 doi.org 独立解析核验（不抓 Google Scholar、不用 CNKI）。中文走 OpenAlex `language=zh` / Crossref 中文期刊 / DOAJ / PubMed 中文医学，优先带 DOI 记录。
- `scripts/make_hallucinations.py`：由真实记录派生 5 类合成幻觉（标题篡改/作者伪造/DOI捏造/venue年份错配/完全虚构），经负向核验确认不对应真实公开记录。
- `data/citation_hallucination.json`：100 条 NeurIPS 2025 GPTZero 真实幻觉引用（`subset=hallucination_gptzero`），来源与许可见各条 `note`。
- `scripts/assemble_dataset.py`：合并去重 + 按来源论文做 dev/test 划分。

## 使用方式

完整生成流程：

```bash
python scripts/collect_real_refs.py
python scripts/make_hallucinations.py
python scripts/assemble_dataset.py
python scripts/build_refguard_input.py
```

仅重新生成评测输入（源文件已就绪时）：

```bash
python scripts/build_refguard_input.py
```

运行小规模 smoke test：

```bash
python eval/run_benchmark.py --input data/refguard_input.jsonl --out tmp_eval_check --limit 1 --sources unknown
```

运行完整评测时会访问公开元数据接口，请遵守各接口的请求频率、API 条款和引用要求。

## 开源边界

本数据用于个人研究和论文实验复现。公开可访问不等于自动可再分发；如将数据用于论文附件、公开 release 或第三方复用，请再次核查来源许可、API 条款和引用要求。
