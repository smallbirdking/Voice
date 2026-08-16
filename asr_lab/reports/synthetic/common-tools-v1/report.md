# ASR 实验聚合报告

## 运行边界

- 状态：`passed`
- 运行：`run-20260816T152615449367Z-9730f8143d18`
- 环境：`env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- Provider：`synthetic`
- 模型：`synthetic-deterministic-v1`
- 语料：`voice-asr-eval:v1`

## 完整性

- 总样本：7
- 成功：7
- 失败或未完成：0

## 指标

| 指标 | 已评估样本 | 分子 | 分母 | 结果 |
| --- | ---: | ---: | ---: | ---: |
| cer | 2 | 0 | 46 | 0.000000 |
| wer | 2 | 0 | 6 | 0.000000 |
| mixed_error | 1 | 0 | 9 | 0.000000 |
| keyword sample hit | 2 | 2 | 2 | 1.000000 |
| silence false recognition | 2 | 0 | 2 | 0.000000 |

## 样本明细

| sample_id | 语言 | 场景 | 状态 | RTF | 错误 |
| --- | --- | --- | --- | ---: | --- |
| zh-short-command-001 | zh-CN | short-command | succeeded | 0.008113 |  |
| zh-long-form-001 | zh-CN | long-form | succeeded | 0.002221 |  |
| en-general-speech-001 | en-US | general-speech | succeeded | 0.015089 |  |
| en-short-command-001 | en-US | short-command | succeeded | 0.007690 |  |
| zh-en-mixed-001 | zh-en | general-speech | succeeded | 0.003664 |  |
| silence-001 | none | silence | succeeded | 0.002892 |  |
| noise-001 | none | noise-only | succeeded | 0.001993 |  |

## 性能摘要

成功样本 RTF：count=7，mean=0.005952，max=0.015089。

失败样本保留在明细和 `failures` 中；准确率只对存在合法识别输出的成功样本计算，失败数量单独报告，未被静默删除。
