# 检查点：语料清单输入契约

## 元数据

- `task_id`: `2.1`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/schemas/corpus-manifest.schema.json`、`asr_lab/src/voice_asr_lab/corpus/manifest.py`、`asr_lab/corpus/manifests/schema-example.json`、`asr_lab/tests/test_corpus_manifest.py`

## 目标

在准备任何真实测试音频前，先固定一份可机器校验的语料清单契约。它必须明确一次比较所用的语料版本，并让每个样本的身份、音频描述、语言场景、参考文本规则和来源许可都可审计。

## 核心概念

- `schema_version` 描述清单文件结构的版本；`corpus_version` 描述音频、文字、标签和规则组成的输入集合版本，两者不能混用。
- JSON Schema 负责字段类型、必填项、枚举、格式和禁止未知字段；Python 语义校验负责 JSON Schema 不便表达的 `sample_id` 唯一性、路径安全和跨字段关系。
- `audio.sha256` 是音频内容地址，能在后续识别内容变化；本步骤只校验摘要的表示格式，不读取文件或声称摘要真实。
- 有语音样本必须有语言、参考文本和规范化版本；`silence` 与 `noise-only` 使用 `language: "none"` 及空参考字段，避免把无文字错误地计入 CER/WER。
- 来源和许可不是说明文档中的一句话，而是每条样本的结构化字段；后续准备语料时必须提供许可标识、再分发状态和证据。

## 入口命令

工作目录：仓库根目录 `D:\workspace\ai\Voice`。

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m voice_asr_lab validate-corpus-manifest asr_lab/corpus/manifests/schema-example.json
python -m unittest discover -s asr_lab/tests -p 'test_corpus_manifest.py' -v
python -m unittest discover -s asr_lab/tests -v
openspec validate evaluate-local-asr-providers --strict
```

## 预期结果

结构示例应在不访问虚构音频路径的情况下通过校验并报告两个样本。缺失摘要、多余字段、重复样本标识、目录逃逸、空清单以及语音和无语音参考字段冲突都应产生明确错误；新增逻辑不应破坏既有环境与网络边界测试。

## 实际输出

```text
{
  "status": "valid",
  "corpus_id": "schema-contract-example",
  "corpus_version": "v1",
  "sample_count": 2,
  "errors": []
}

Ran 9 tests in 0.006s
OK

Ran 48 tests in 1.780s
OK

Change 'evaluate-local-asr-providers' is valid
```

专项测试还逐项验证了重复 `sample_id`、`source/../outside.wav`、Windows 绝对路径、反斜杠路径、重复分隔符、空清单、参考字段冲突和非法 JSON 均被拒绝。

## 结果解释

结果证明清单能够作为版本化、Provider 无关的输入契约，也证明 CLI 的成功与失败输出都可被后续自动化读取。`schema-example.json` 只是两个字段组合的教学样例，不是 v1 评测语料；本步骤没有验证任何音频存在、SHA-256 正确或 WAV 头与声明一致，因此不能替代任务 2.2 和 2.3。

## 遇到的问题

实验台的轻量 JSON Schema 校验器原先没有实现 `minItems`，导致空语料清单无法被结构层拒绝。本步骤只补充了所需的 `minItems` 子集并增加回归测试，没有引入第三方运行依赖。路径库会自动折叠 `//` 和 `/./`，所以语义校验同时要求规范化后的 POSIX 路径与原字符串完全一致。

## 进入下一步的条件

- [x] 清单 Schema 覆盖任务要求的所有字段并拒绝未知字段。
- [x] 稳定样本标识、相对路径和语音/无语音跨字段规则有自动测试。
- [x] 来源许可为逐样本必填结构，能在准备真实语料时逐条登记。
- [x] 专项测试、完整回归和 OpenSpec 严格校验全部通过。
- [x] 明确保留真实音频准备给 2.2、媒体与摘要核验给 2.3。
