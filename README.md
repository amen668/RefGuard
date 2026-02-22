# RefGuard

Reference Integrity & Citation Quality Checker — 面向数据源的证据融合（source-aware evidence fusion）一体化工具。

- **Mode A**：Bib-only，参考文献存在性与元数据一致性检查。
- **Mode B**：Bib+TeX，引用用法检查与可选 LLM 相关性评估。

核心方法：多源候选生成 → 特征化 → 证据融合器输出 P(match) → 概率阈值决策；LLM 仅用于语义相关性，不参与存在性判定。

- Python 3.11+
- 部署：Docker，Linux x86_64
- 接口：HTTP API + CLI (`refcheck`)

## 安装依赖

在项目根目录执行（注意是 `-r`，表示从文件安装）：

```bash
pip install -r requirements.txt
```

或安装为可编辑包（推荐，便于开发）：

```bash
pip install -e .
```

## 快速开始

```bash
# CLI Mode A
refcheck verify bib --input ./refs.bib --profile strict --out ./report/

# CLI Mode B
refcheck verify project --bib ./paper/references.bib --tex ./paper/main.tex --check-usage on --out ./report/
```

## 如何测试

### 1. API 测试（需先启动服务：`uvicorn main:app --reload`）

- **接口文档**：浏览器打开 http://127.0.0.1:8000/docs 或 http://127.0.0.1:8000/redoc
- **健康/状态**：GET http://127.0.0.1:8000/api/v1/sources/status（查看缓存与数据源列表）
- **Bib 验证**：POST http://127.0.0.1:8000/api/v1/verify/bib，Body 示例见下方

PowerShell 示例（验证一条 BibTeX）：

```powershell
$body = @{
  bibtex_content = "@article{test2020, title={Test Paper}, author={Author, First}, year={2020}, journal={Test Journal}}"
  profile = "balanced"
  options = @{ check_duplicates = $true; top_k_candidates = 8 }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/verify/bib" -Method Post -Body $body -ContentType "application/json; charset=utf-8"
```

或用 curl（Git Bash / WSL）：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/verify/bib" -H "Content-Type: application/json" -d "{\"bibtex_content\": \"@article{test2020, title={Test Paper}, author={Author, First}, year={2020}}\", \"profile\": \"balanced\"}"
```

### 2. CLI 测试

用项目自带的示例 Bib 文件：

```bash
refcheck verify bib --input tests/test_bib.bib --profile balanced --out ./report/
```

完成后查看 `./report/report.json` 和 `./report/report.md`。

### 3. 自动化测试（pytest）

安装 dev 依赖后运行项目内测试：

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## 许可证

GPL-3.0-or-later。详见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
