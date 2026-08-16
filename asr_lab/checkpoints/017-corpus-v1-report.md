# 检查点：v1 语料覆盖与质量报告

## 元数据

- `task_id`: `2.9`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/reports/corpus/voice-asr-eval-v1-summary.json`、`asr_lab/reports/corpus/voice-asr-eval-v1-summary.md`、`asr_lab/tests/test_corpus_report.py`

## 目标

完成第二部分的总验收：一次命令同时校验清单、源音频、派生输入、规范化、指纹、最低场景覆盖和许可边界，并保留 JSON 与 Markdown 两种一致报告。

## 核心概念

- 报告不能只统计成功文件而丢弃失败样本；样本集合必须与清单完全一致。
- JSON 保存机器后续使用的逐样本事实，Markdown 提供学习和人工审核入口。
- 两份报告共享同一 `corpus_version`、`corpus_fingerprint` 和样本数量。
- 任一源文件、派生文件、清单规则或最低覆盖失败时，命令返回失败且不写“成功报告”。
- 报告采用拒绝覆盖语义，避免重跑时销毁旧实验边界证据。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m voice_asr_lab report-corpus asr_lab/corpus/manifests/voice-asr-eval-v1.json `
  --derived-root asr_lab/corpus/derived/v1 `
  --output-json asr_lab/reports/corpus/voice-asr-eval-v1-summary.json `
  --output-markdown asr_lab/reports/corpus/voice-asr-eval-v1-summary.md
python -m unittest discover -s asr_lab/tests -p 'test_corpus_report.py' -v
```

## 预期结果

七种最低覆盖全部满足，七个源音频和七个派生音频全部通过，报告无错误；许可汇总明确揭示非商业限制。

## 实际输出

```text
status=saved
corpus_id=voice-asr-eval
corpus_version=v1
corpus_fingerprint=corpus-sha256-46f7d367fe4b7605cdf2a0d8e4a76643b24aa911c5b49e889d0eb4df3472620b
sample_count=7
total_duration_ms=20297
coverage_complete=true
source_audio=7/7 passed
derived_audio=7/7 passed
errors=0

Ran 6 tests in 0.072s
OK
```

## 结果解释

v1 已成为可以交给每个 ASR Provider 的固定输入边界。中文、英文、中英混合、静音、噪声、长句和短命令都有覆盖；所有派生输入都是同一算法生成的 16kHz 单声道 PCM16。

## 遇到的问题

中文和混合的三条录音使用 CC BY-NC 4.0，因此报告明确保存 `commercial_use_ready=false`。这不是技术失败，而是使用边界：当前集合适合本地学习与非商业评测，商用前必须替换三条受限样本并发布新版本和新指纹。

## 进入下一步的条件

- [x] 清单、源音频与派生音频全部通过。
- [x] 七种最低语言/场景覆盖全部满足。
- [x] JSON 和 Markdown 共享同一版本指纹与样本数。
- [x] 所有样本均保留，失败不会被静默过滤。
- [x] 非商业许可边界明确进入报告。
- [x] 第二部分完整回归通过后才进入 3.1。
