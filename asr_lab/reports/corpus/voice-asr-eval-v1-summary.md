# Voice ASR v1 语料覆盖与质量报告

## 结论

- 状态：`passed`
- 语料边界：`voice-asr-eval:v1`
- 内容指纹：`corpus-sha256-46f7d367fe4b7605cdf2a0d8e4a76643b24aa911c5b49e889d0eb4df3472620b`
- 样本数：7；总时长：20297 ms
- 源音频：7/7 通过
- 派生音频：7/7 通过
- 规范化版本：text-normalization-v1

## 必需覆盖

| 维度 | 是否覆盖 |
| --- | --- |
| chinese | 是 |
| english | 是 |
| mixed_chinese_english | 是 |
| silence | 是 |
| noise | 是 |
| long_form | 是 |
| short_command | 是 |

## 样本明细

| sample_id | 语言 | 场景 | 源音频 | 16kHz 派生音频 | 许可再分发 |
| --- | --- | --- | --- | --- | --- |
| zh-short-command-001 | zh-CN | short-command | passed | passed | restricted |
| zh-long-form-001 | zh-CN | long-form | passed | passed | restricted |
| en-general-speech-001 | en-US | general-speech | passed | passed | allowed |
| en-short-command-001 | en-US | short-command | passed | passed | allowed |
| zh-en-mixed-001 | zh-en | general-speech | passed | passed | restricted |
| silence-001 | none | silence | passed | passed | allowed |
| noise-001 | none | noise-only | passed | passed | allowed |

## 许可边界

受限样本共 3 个：`zh-short-command-001`, `zh-long-form-001`, `zh-en-mixed-001`。

`commercial_use_ready=false` 表示当前 v1 含 CC BY-NC 音频，仅适合本地学习和非商业评测；商用前必须替换受限样本并创建新语料版本与指纹。

## 验证说明

派生输入统一采用 `pcm16-mono-linear-v1`：16kHz、单声道、PCM16。JSON 报告保留每个源文件和派生文件的实际摘要、帧数、时长、规范化文本、语言片段与许可证据。
