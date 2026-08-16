# 检查点：确定性音频预处理

## 元数据

- `task_id`: `2.4`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/corpus/preprocessing.py`、`asr_lab/tests/test_preprocessing.py`、`asr_lab/corpus/derived/v1/`

## 目标

把不同采样率和声道布局的源 WAV 统一为 Provider 可复用的 16kHz、单声道、PCM16 输入，同时保证算法确定、重复运行可验证、源文件绝不被覆盖。

## 核心概念

- 双声道或多声道按每帧整数平均下混，避免平台浮点差异。
- 重采样使用版本化的整数线性插值 `pcm16-mono-linear-v1`，有符号除法采用固定的“半数远离零”舍入。
- 输出帧数由 `round(source_frames * 16000 / source_rate)` 得出，时长再从实际输出帧计算。
- 输出目录是可重建缓存；已存在的目标立即失败，目标与任一源文件重合也立即失败。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m voice_asr_lab preprocess-corpus asr_lab/corpus/manifests/voice-asr-eval-v1.json --output-root asr_lab/corpus/derived/v1
python -m unittest discover -s asr_lab/tests -p 'test_preprocessing.py' -v
```

## 预期结果

七个样本全部生成 16kHz 单声道 PCM16 WAV；在两个空目录重复生成时，每个同名文件的 SHA-256 相同；原始语料的 SHA-256 与清单仍一致。

## 实际输出

```text
preprocess-corpus:
  status=created
  algorithm=pcm16-mono-linear-v1
  sample_count=7
  all outputs: wav / pcm-s16le / 16000 Hz / mono / 16 bit

Ran 5 tests in 0.278s
OK
```

七个输出摘要依次为：

```text
zh-short-command-001  3f5ebd192bf6ced2b3e6d121e2b5012130c7d70eeaf36180232ed307f524f95c
zh-long-form-001      eca85ebbbae9559af2867395b78a9e781b9f22702b3620db641bbec41bedf8a6
en-general-speech-001 6c1274c9e6d0a15f4c5887762d01f0662bbd0e3e1a8596ef32e8f70ec420bb44
en-short-command-001  aeb550c5124468ae74a020b0e90f13d1703c196a5326d64c6ce20560117a5c0f
zh-en-mixed-001       de6e0bbb8dab733076af77263c3f691b14362162fdaebdc429432a9d0bca2f5d
silence-001           20eaebffe1816e0ffa6f7f854f5ef4ea80d5349faaf0ce1fec1b713e7fde58fa
noise-001             1f38d191d4217943cb0942cda25074c3a6b1f1bcc95ae8574b0df7ec1c2afd7d
```

## 结果解释

摘要一致性测试证明结果由输入字节和明确算法决定，而不是由临时目录或执行次数决定。输出目录被 `.gitignore` 排除，因为它可以从受版本控制的源语料重新生成；最终报告会保存派生摘要作为复现证据。

## 遇到的问题

Python 3.13 已弃用、3.14 已移除 `audioop`，因此没有把实验建立在该模块上。实现只使用 `wave`、`array` 和整数运算，避免新增运行时依赖。

## 进入下一步的条件

- [x] 七个样本均生成统一媒体格式。
- [x] 两次独立生成得到相同摘要。
- [x] 源摘要在预处理前后保持一致。
- [x] 已存在输出和源路径重合都被拒绝。
- [x] 下混、重采样和边界样值均有单元测试。
