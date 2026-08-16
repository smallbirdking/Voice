# 检查点：合成 Provider 端到端实验

## 元数据

- `task_id`: `3.9`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/reports/synthetic/common-tools-v1/`、`asr_lab/src/voice_asr_lab/experiment/pipeline.py`、`asr_lab/tests/test_synthetic_pipeline.py`

## 目标

把第三阶段的事件、计时、合成 Provider、离线回放、资源采样、指标和报告工具组合成一次完整 v1 语料实验，保留可执行入口、原始事实、派生指标和字段解释。

## 核心概念

- 组合管线不绕过任何独立契约：每个事件流、资源采样和逐样本结果在写盘前重新校验。
- 每个 v1 派生 WAV 先经过离线回放并验证 PCM 字节往返一致，再交给合成 Provider。
- 每个样本在 Provider 前后各采一次资源，逐样本结果只保存两个稳定引用。
- 七个事件文件按样本/会话分开，避免把多个会话误当成一条连续流。
- 聚合报告从逐样本事实和同指纹语料参考计算，不回写原始记录。
- `synthetic` 的完美准确率只证明公共管线，不能当作真实模型结论。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m voice_asr_lab run-synthetic-experiment `
  asr_lab/corpus/manifests/voice-asr-eval-v1.json `
  --derived-root asr_lab/corpus/derived/v1 `
  --environment-baseline asr_lab/reports/baselines/environment-baseline-v1.json `
  --output-dir asr_lab/reports/synthetic/common-tools-v1
python -m unittest asr_lab.tests.test_synthetic_pipeline asr_lab.tests.test_stream_events asr_lab.tests.test_cli_architecture -v
```

## 预期结果

完整 v1 的 7 个样本都应生成事件、两条资源采样和一条逐样本结果；报告无失败，合成文字与参考一致，静音与噪声不产生文字。输出目录已存在时必须拒绝覆盖。

## 实际输出

```text
run_id=run-20260816T152615449367Z-9730f8143d18
status=passed
samples=7, succeeded=7, failed=0
event_files=7, events=59
resource_samples=14, resource_error_samples=0
gpu_statuses=[available]
cer=0.0, wer=0.0, mixed_error=0.0
silence_false_recognition_samples=0

Ran 14 tests in 0.177s
OK
```

## 结果解释

第三阶段的所有公共组件已经在同一真实入口中协作：运行上下文固定环境，回放器读取 v1 派生输入，合成 Provider 产生事实事件，资源采样与结果通过 ID 关联，聚合层重新计算指标，JSON 和 Markdown 保存相同实验结论。输出目录中的 `README.md` 逐项说明各文件职责。

这些结果没有加载 ASR 模型，因此 0 错误率是受控测试数据，不表示任何候选的识别能力。它建立的是后续 FunASR、sherpa-onnx、faster-whisper 和 NVIDIA 实验共用的测量基线。

## 遇到的问题

第一次真实运行暴露 Windows RSS 探针未声明 WinAPI 64 位句柄签名，14 条采样都正确保留了 `GetProcessMemoryInfo failed`，实验本身没有中断。修复函数签名并增加真实进程探针测试后，旧运行移动到被 Git 忽略的 `asr_lab/tmp/synthetic-common-tools-v1-process-probe-failed`，正式路径重新运行得到 14 条无错误资源采样。端到端测试还发现静音 final 应允许空字符串，校验器已限定为仅 partial 必须非空。

## 进入下一步的条件

- [x] v1 七个样本全部通过同一端到端入口且没有丢失。
- [x] 59 条事件、14 条资源采样和 7 条逐样本结果均可关联与校验。
- [x] JSON、Markdown 和字段学习索引已保存到可追踪报告目录。
- [x] 真实 Windows RSS、可用 GPU 和静音 final 边界均有回归证据。
- [x] 第三阶段完整，可以进入任务 4.1：FunASR 权威来源预检。
