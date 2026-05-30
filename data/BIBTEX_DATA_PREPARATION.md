# 真实文献 BibTeX 数据整理指南

本文档用于整理后续从真实文献中收集的 BibTeX 记录，并把它们合并到 RefGuard 基准数据。目标是让每条“真实文献”都能被公开学术元数据源复核，同时保留清楚的来源和许可边界。

## 总原则

- 只收集公开可访问的书目信息：题名、作者、年份、期刊/会议、DOI、arXiv ID、URL、BibTeX 条目来源。
- 不保存论文全文、PDF、用户上传文件、账号登录后导出的私有数据、cookie、API key 或内部数据。
- 优先使用 DOI、arXiv、OpenAlex、Crossref、DBLP、出版社页面等可复核来源。
- 每条真实文献至少保留一个可公开访问的核验线索，优先级为 DOI > arXiv ID > 出版社/会议页面 URL > OpenAlex/Crossref/DBLP URL。
- 不要把“搜索得到过”当作证据；需要记录具体来源 URL 或稳定标识符。

## 建议工作流

1. 收集候选 BibTeX

   从论文官网、出版社页面、DBLP、arXiv、Crossref、OpenAlex 或作者主页获取 BibTeX。避免从不清楚许可和来源的批量爬取结果直接导入。

2. 建立原始暂存表

   建议先用 CSV、JSON 或电子表格暂存，字段见下方“整理字段”。原始 BibTeX 可以放在本地临时文件中，不一定提交；提交前只保留项目需要的结构化书目信息和来源说明。

3. 规范化字段

   统一作者、年份、DOI、arXiv ID 和 URL。删除明显的占位符、访问参数、跟踪参数和重复空格。中文文献保留中文题名，必要时在备注中记录英文译名来源。

4. 人工核验

   对每条记录检查题名、作者、年份是否和 DOI/arXiv/出版社页面一致。DOI 缺失但其他来源可核验的记录也可以保留，但需要写明 `verification_status`。

5. 合并到源数据

   将整理后的真实文献加入 `data/citation_dataset_final_v4.json` 或后续版本源文件，再运行：

   ```bash
   python scripts/build_refguard_input.py
   ```

6. 检查生成摘要

   查看 `data/refguard_input_summary.json`，确认总数、标签分布、缺失字段、重复 ID 和 placeholder URL。缺失字段为 0 后，再考虑提交生成后的 `data/refguard_input.jsonl`。

## 整理字段

源数据建议保留这些字段。字段名应和当前 `scripts/build_refguard_input.py` 兼容，减少后续转换成本。

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 全局唯一 ID，建议使用稳定前缀，如 `real_bibtex_0001`。 |
| `label` | 是 | 真实文献填写 `real`。 |
| `title` | 是 | 参考文献题名，和公开来源保持一致。 |
| `authors` | 是 | 作者字符串；多人可用 `and`、英文逗号或中文顿号分隔。 |
| `year` | 是 | 发表年份。 |
| `venue` | 建议 | 期刊、会议、预印本平台、出版社或报告机构。 |
| `doi` | 建议 | DOI 原文，不要加 `https://doi.org/` 前缀。 |
| `arxiv_id` | 可选 | arXiv 编号，例如 `1706.03762`。 |
| `url` | 建议 | 参考文献自身的公开页面。 |
| `citation_text` | 建议 | 原始参考文献文本或由字段拼出的可读 citation。 |
| `source_paper` | 可选 | 如果来自某篇源论文的参考文献列表，记录源论文题名。 |
| `source_paper_url` | 可选 | 源论文公开 URL。 |
| `language` | 建议 | `English`、`Chinese` 等。 |
| `doc_type` | 建议 | `journal`、`conference`、`preprint`、`book`、`thesis`、`technical_report` 等。 |
| `discipline` | 可选 | 学科或主题。 |
| `subset` | 建议 | 真实公开元数据可用 `real_public_metadata`。 |
| `verification_status` | 是 | 建议用 `verifiable_via_public_metadata`。 |
| `verifiable` | 是 | 真实文献通常为 `true`。 |
| `note` | 可选 | 记录人工核验说明、异常情况或来源限制。 |

## 单条记录模板

```json
{
  "id": "real_bibtex_0001",
  "label": "real",
  "title": "Attention Is All You Need",
  "authors": "Vaswani, Ashish and Shazeer, Noam and Parmar, Niki and Uszkoreit, Jakob and Jones, Llion and Gomez, Aidan N. and Kaiser, Lukasz and Polosukhin, Illia",
  "year": 2017,
  "venue": "Advances in Neural Information Processing Systems",
  "doi": "",
  "arxiv_id": "1706.03762",
  "url": "https://arxiv.org/abs/1706.03762",
  "citation_text": "Vaswani, Ashish, et al. Attention Is All You Need. Advances in Neural Information Processing Systems, 2017. arXiv:1706.03762.",
  "source_paper": "",
  "source_paper_url": "",
  "language": "English",
  "doc_type": "conference",
  "discipline": "Computer Science",
  "subset": "real_public_metadata",
  "verification_status": "verifiable_via_public_metadata",
  "verifiable": true,
  "note": "BibTeX/source metadata checked against arXiv public page."
}
```

## BibTeX 清洗规则

- 保留 BibTeX key 仅作临时追踪，不把它当作稳定论文 ID。
- DOI 统一去掉 URL 前缀，去掉尾部句号和空格。
- arXiv ID 统一去掉 `arXiv:` 前缀；旧格式保留分类前缀，如 `cmp-lg/9705013`。
- 作者不要只保留 `et al.`；至少在结构化 `authors` 中保留完整作者列表。
- 年份只保留四位数字；在线优先、正式出版年份不一致时，在 `note` 中说明选择。
- URL 优先使用稳定详情页，不使用搜索结果页、带 session 的链接、带登录跳转的链接或镜像站。
- 中文文献如果来自需要登录或授权的平台，不要提交平台导出内容；只提交可公开核验的书目信息和公开来源 URL。

## 质量检查清单

提交前逐项确认：

- `id` 没有重复。
- `label` 全部为 `real`，没有混入幻觉样本。
- `title`、`authors`、`year`、`verification_status` 不为空。
- 至少存在 `doi`、`arxiv_id`、`url` 中的一个。
- 没有 `PLACEHOLDER`、`TODO`、`example.com`、本地路径或私有网盘链接。
- 没有 PDF 全文、摘要大段复制、API 原始响应或登录后导出字段。
- `python scripts/build_refguard_input.py` 生成的 summary 中 `duplicate_ids` 为 0，`placeholder_urls` 为 0，关键字段 missing 为 0。

## 提交建议

一次数据提交最好同时包含：

- 更新后的源数据文件。
- 重新生成的 `data/refguard_input.jsonl`。
- 重新生成的 `data/refguard_input_summary.json`。
- 必要时更新 `data/DATASET_CARD.md` 中的总数、标签分布、语言分布和来源边界说明。

如果新增数据来自多个来源，建议在提交说明里写清楚来源类型，例如 “add 120 real references from arXiv and Crossref metadata”。不要在提交信息里写入任何私有链接或账号相关信息。
