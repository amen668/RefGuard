# 数据目录

本目录用于放置公开样例和可复现实验记录。当前项目数据来自公开来源和公开元数据。

公开可访问不等于自动可再分发。用于论文附件、公开 release 或第三方复用前，请逐项核查来源许可、API 条款和引用要求。

可以提交：

- 题名、作者、年份、期刊/会议、DOI、arXiv ID、URL 等公开书目信息。
- 项目自行标注或允许再分发的标签与说明。
- 公开来源的 provenance 字段。

不要提交：

- API key、access token、cookie 或其他私人凭据。
- 用户上传的论文原文或全文论文。
- 非公开数据源导出。
- 需要登录、授权、cookie 或工作账号才能访问的数据源内容。
- 没有明确再分发许可的大型原始数据集。

## 当前文件

- `citation_dataset_final_v4.json`：V4 源数据，共 1147 条，其中真实文献 939 条、幻觉文献 208 条。
- `refguard_input.jsonl`：正式基准输入，共 1147 条，其中真实文献 939 条、幻觉文献 208 条。
- `refguard_input_summary.json`：由生成脚本输出的数据质量摘要。
- `DATASET_CARD.md`：数据集字段、标签和使用边界说明。
- `BIBTEX_DATA_PREPARATION.md`：后续整理真实文献 BibTeX 的字段、清洗和核验流程。

## 生成方式

`refguard_input.jsonl` 由源数据自动生成，不手工维护：

```bash
python scripts/build_refguard_input.py
```

生成脚本会规范作者列表、补齐参考文献原始文本、清理占位链接，并检查关键字段缺失、重复 ID 和 placeholder URL。

正式用于论文附件或公开 release 前，请再次核查其来源、许可和可再分发性。
