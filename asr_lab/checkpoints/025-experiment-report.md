# 检查点：逐样本 JSONL 聚合报告

## 元数据

- `task_id`: `3.8`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/experiment/report.py`、`asr_lab/tests/test_experiment_report.py`、`asr_lab/src/voice_asr_lab/commands/experiment.py`

## 目标

从有效逐样本 JSONL 和对应版本化语料清单生成聚合 JSON 与 Markdown，计算指标并保证失败样本仍出现在总数、明细和失败证据中。

## 核心概念

- 原始结果只保存事实；聚合时从清单取得规范化参考，再调用任务 3.7 的纯指标函数。
- 同一报告的结果必须共享运行、环境、Provider、模型和语料指纹。
- 样本 ID 必须唯一且存在于清单，语言和场景不得与清单漂移。
- 失败样本没有合法识别输出，所以不伪造准确率，但进入 `failed_count`、样本明细和 `failures`。
- 加权错误率汇总编辑距离和参考单元后再相除，不简单平均每条样本百分比。
- JSON 与 Markdown 独占写入，避免重跑覆盖旧证据。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m voice_asr_lab aggregate-results results.jsonl `
  asr_lab/corpus/manifests/voice-asr-eval-v1.json `
  --output-json report.json --output-markdown report.md
python -m unittest asr_lab.tests.test_experiment_report asr_lab.tests.test_metrics asr_lab.tests.test_cli_architecture -v
```

## 预期结果

一个中文成功样本和一个英文失败样本应生成 `completed_with_failures` 报告，总数 2、成功 1、失败 1；中文 CER 为 0，英文 WER 不应被错误记成 0，Markdown 必须列出失败样本与错误代码。

## 实际输出

```text
status=completed_with_failures
sample_count=2
succeeded_count=1
failed_count=1
cer_rate=0.0
wer_evaluated_samples=0
failed_sample=en-general-speech-001
markdown_contains_configured_failure=true

Ran 16 tests in 0.018s
OK
```

## 结果解释

报告层现在清楚地区分“没有错误”和“因为执行失败而没有指标”。JSON 适合后续横向比较，Markdown 让学习者直接检查运行边界、完整性、指标、样本状态和错误。

## 遇到的问题

仅凭逐样本结果无法取得完整参考文字，而把参考复制进每次结果会增加漂移风险。因此命令显式接收语料清单，并核对结果中的语料指纹、语言和场景后再计算指标。

## 进入下一步的条件

- [x] JSONL 每行在聚合前通过逐样本契约。
- [x] 跨样本运行、环境、Provider、模型和语料边界得到核对。
- [x] 失败样本完整保留且不制造虚假准确率。
- [x] JSON 与 Markdown 同时生成并拒绝覆盖。
- [x] 可以进入任务 3.9：组合所有公共组件完成一次端到端合成实验。
