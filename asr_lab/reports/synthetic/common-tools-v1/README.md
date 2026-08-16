# 合成 Provider 端到端实验

## 入口命令

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab run-synthetic-experiment asr_lab/corpus/manifests/voice-asr-eval-v1.json `
  --derived-root asr_lab/corpus/derived/v1 `
  --environment-baseline asr_lab/reports/baselines/environment-baseline-v1.json `
  --output-dir <new-output-directory>
```

## 文件与字段

- `run-context.json`：一次运行及其精确环境快照关联。
- `events/<sample_id>.jsonl`：partial、endpoint、final、取消和关闭等不可变流式事实。
- `resource-samples.jsonl`：CPU、RSS、GPU 或采集错误；逐样本结果使用 ID 引用。
- `sample-results.jsonl`：输入、Provider、模型、配置、文字、时间和 outcome 原始事实。
- `replay-summaries.json`：离线回放的块数、字节数、音频时长与逻辑耗时。
- `report.json`：从事实与语料参考派生的准确率、RTF、完整性和失败清单。
- `report.md`：相同报告的人工学习视图。

本次运行 `run-20260816T152615449367Z-9730f8143d18` 共处理 7 个样本，保存
59 条事件；成功 7，
失败 0。`synthetic` 只证明公共工具管线，不证明真实 ASR 能力。
