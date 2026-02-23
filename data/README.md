# 基准数据目录

将 **refguard_input.jsonl** 放在此目录下，用于 RefGuard 幻觉引用基准测试。

## 使用方式

1. 把从 RefGuard Full Benchmark 生成的 `refguard_input.jsonl` 复制到本目录（或保持当前已有文件）。
2. 在项目根目录执行：

   **先跑 10 条试跑：**
   ```bash
   python eval/run_benchmark.py --limit 10
   ```
   或显式指定输入：`python eval/run_benchmark.py --input data/refguard_input.jsonl --out ./eval_report --limit 10`

   **跑全部 100 条：**
   ```bash
   python eval/run_benchmark.py
   ```

3. 结果输出在项目根目录的 `eval_report/` 下（eval_report.json、eval_report.md）。
