# RefGuard 基准数据卡

> **版本提示（2026-09-01）**：`citation_dataset_public_v4.json` 是录用稿结果的
> 冻结历史快照，不再静默改写。录用后书目身份校正版为
> `citation_dataset_public_v5_core.json`，由 `corrections_v5.json` 确定性生成。
> 因尚未取得 GPTZero 第三方数据的再分发许可，公开 V5 核心集排除了该100条
> 子集，规模为2,437条；因此V5不能直接复现录用稿的2,537条结果。版本边界见
> `VERSION_HISTORY.md`。

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

## 伦理声明与使用限制（重要）

本数据集包含**人工合成的"幻觉"参考文献**（负样本），其唯一用途是作为引用真实性检测的**基准负例**。

- ⚠️ **合成负样本（500 条，`subset=hallucination_synthetic`）是刻意构造的虚假引用**（篡改题名 / 伪造作者 / 捏造 DOI / 错配 venue/年份 / 完全虚构）。它们**不指向真实文献**，**严禁**被当作真实参考文献引用、转引或写入任何论文的参考文献表。每条均带 `label=hallucination`、`hallucination_type` 与 `note`（构造方法），便于审计。
- 合成假作者名为占位用途，**不影射任何真实个人**；如发现偶然撞名，请提 issue 移除。
- 真实样本（`label=real`）仅含公开书目元数据，其"真实"标签由 DOI 经 doi.org 独立解析确立，**不**由 RefGuard 自身判定（避免循环标注）。

## 第三方来源与许可（公开发布前必读）

| 子集 | 来源 | 许可 / 再分发注意 |
| --- | --- | --- |
| `hallucination_synthetic`（500）| 本项目由真实引用派生合成 | 可随项目以 CC-BY/CC0 发布；须保留伦理声明 |
| 真实样本（1937）| Crossref / OpenAlex / arXiv / DBLP（多为 CC0）| 纯书目事实，再分发风险低；注明来源即可 |
| `hallucination_gptzero`（100）| **第三方 GPTZero 报告**（NeurIPS 2025）| ⚠️ **再分发前须核查 GPTZero 条款**。建议署名并链接其报告；公开版应剥离 `gptzero_comment`（其原始判定文字），可用 `scripts/make_public_dataset.py` 处理 |

## 公开发布清单（release checklist）

正式公开数据集前逐项确认：

1. [ ] 运行 `scripts/build_corrected_v5.py` 生成公开校正核心集及校验报告。
2. [ ] 确认公开产物中 `hallucination_gptzero` 记录数为0；未获许可前不得恢复。
3. [ ] 确认仅含书目字段，无摘要 / 全文 / 凭据 / cookie / API 原始响应。
4. [ ] 附本数据卡与 `LICENSE`，明确合成负样本的使用限制。
5. [ ] 在Release说明中同时给出V4冻结哈希、V5校正哈希及二者结果不可混用的声明。

## 开源边界

本数据用于个人研究和论文实验复现。公开可访问不等于自动可再分发；如将数据用于论文附件、公开 release 或第三方复用，请再次核查来源许可、API 条款和引用要求。
