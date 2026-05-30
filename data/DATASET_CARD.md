# RefGuard 基准数据卡

## 基本信息

`refguard_input.jsonl` 是 RefGuard 的论文实验基准数据，由 `citation_dataset_final_v4.json` 通过 `scripts/build_refguard_input.py` 生成。源数据与当前评测输入均为 1147 条参考文献记录。

标签分布：

- 真实文献：939 条
- 幻觉文献：208 条

语言分布：

- 英文文献：1067 条
- 中文文献：80 条（真实 40 条、幻觉 40 条）

数据仅包含书目信息、核验标签和必要元数据，不包含论文全文、用户上传文件、账号凭据、cookie 或 API 原始响应。

生成后的数据质量摘要见 `refguard_input_summary.json`：当前版本无重复 ID、无 placeholder URL，关键字段无缺失。此前公开复核性不足的 CNKI 记录已从源数据中移除。

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
- `meta`：语言、文献类型、学科、幻觉类型等实验元数据。

## 使用方式

重新生成评测输入：

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
