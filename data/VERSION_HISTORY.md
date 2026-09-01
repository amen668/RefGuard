# RefGuard 数据版本边界

## V4：录用稿冻结版本

- 文件：`citation_dataset_public_v4.json`
- SHA-256：`c43319ccbaee863db87b250f3a3249234ee500ffb58ff2236a3bd12e2da738a7`
- Git 标签：`paper-v5-frozen-20260901`
- 规模：2,537 条（真实 1,937 / 幻觉 600；开发 500 / 测试 2,037）
- 用途：仅用于解释和复现录用稿冻结结果，TP=472、FP=6、TN=1,559、FN=0。

V4 是历史实验快照，不因录用后的数据质量审计而静默覆盖。其书目字段已知存在
28 条需要校正的记录，详见 `corrections_v5.json`。V4 中包含来源于 GPTZero 报告
的第三方子集；在未取得再分发许可的情况下，不应继续作为默认公开下载数据。

## V5：录用后数据质量校正版

- 文件：`citation_dataset_public_v5_core.json`
- SHA-256：`a121d9fbf757861245ff4daafb2f93fbe66213c04790fce481f5ff8407e7c755`
- 修正清单：`corrections_v5.json`
- 身份审计状态：`verification_provenance_v5.json`
- 生成命令：`python scripts/build_corrected_v5.py`
- 规模：2,437 条（真实 1,937 / 本项目合成负例 500）
- 第三方边界：排除全部 100 条 `hallucination_gptzero` 记录，仅在本文档中保留
  原报告链接：<https://gptzero.me/news/neurips/>。

V5 不替代V4，也不直接复现录用稿指标。任何基于V5的新指标必须另行完成评测，
并明确标为“录用后校正版复评结果”。此前校正过程中的运行结果不得冒充当前代码
的最终结果。

## 数据划分限制

V4/V5 均保持原开发集和测试集划分。`source_paper` 分组没有跨划分，但静态复核
发现14组规范化题名跨划分重复，其中7组题名和作者均重复，因此不宣称严格的
实体级零泄漏。
