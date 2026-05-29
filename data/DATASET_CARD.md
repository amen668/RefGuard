# RefGuard 基准数据说明

## 状态

本目录中的基准数据来自公开来源和公开元数据，应被视为研究数据，而不是自动可再分发的数据集。公开可访问不等于自动可再分发；正式公开完整数据集前，应逐项核查来源许可、API 条款和引用要求。

公开 release 前请确认：

- 每条来源记录都来自公开来源，并已核查可按当前字段形式再分发。
- 标签和说明由项目自行撰写，或具有可再分发许可。
- 不包含私人论文、API 原始响应、cookie、凭据或非公开数据源导出。
- 不包含需要登录、授权、cookie 或工作账号才能访问的数据源派生内容及抓取结果。

## 推荐公开形式

仓库中建议：

- 保留小规模 JSONL 样例，用于 smoke test 和示例。
- 完整基准数据在许可明确前，不随默认包发布。

论文附件建议：

- 发布冻结版本的基准数据归档，包含数据版本、许可、来源说明和评测脚本。
- 提供足够复现实验的元数据，但不分发受版权保护的全文内容。

## JSONL 字段

期望字段：

- `paper_id`
- `paper_title`
- `paper_url`
- `reference.raw`
- `reference.parsed.title`
- `reference.parsed.authors`
- `reference.parsed.year`
- `reference.parsed.venue`
- `reference.parsed.doi`
- `reference.parsed.arxiv`
- `reference.parsed.url`
- `ground_truth.is_hallucinated`
- `ground_truth.notes`
- `source`
