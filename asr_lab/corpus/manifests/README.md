# 语料清单

`schema-example.json` 是任务 2.1 的结构示例，不是可运行的 v1 评测语料，也不对应真实音频。
它展示了有语音与无语音样本如何共同遵守
`schemas/corpus-manifest.schema.json`。

清单中的 `audio.path` 始终相对于 `asr_lab/corpus`，使用 `/` 分隔并位于 `source/`
之下。`audio.sha256` 描述原始文件内容；`check-corpus-audio` 读取真实 WAV 并核对文件存在性、
摘要、格式、采样率、声道、位宽和时长。

有语音样本必须声明语言、非空参考文本、规范化规则版本、规范化文本和带字符区间的语言
片段。校验器会按登记版本重新计算这些派生文字。`silence` 和 `noise-only` 样本使用
`language: "none"`，文字字段设为 `null`，片段数组为空。

`corpus_fingerprint` 是比较相关内容的规范化 JSON SHA-256；人工版本标签和创建时间不参与
指纹。比较时必须同时保存 `corpus_version` 与 `corpus_fingerprint`。

`voice-asr-eval-v1.json` 是实际 v1 语料清单。它包含 7 条小型样本，并明确受
`CC BY-NC 4.0` 限制，只能用于当前非商业学习和评测。完整来源、署名、上游文件摘要与
生成方式见 `../SOURCES.md` 和 `../sources/tatoeba-v1-selection.json`。

运行结构校验：

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab validate-corpus-manifest asr_lab/corpus/manifests/schema-example.json
python -m voice_asr_lab check-corpus-audio asr_lab/corpus/manifests/voice-asr-eval-v1.json
python -m voice_asr_lab fingerprint-corpus-manifest asr_lab/corpus/manifests/voice-asr-eval-v1.json
```
