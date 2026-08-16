# 检查点：语料内容指纹

## 元数据

- `task_id`: `2.8`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/corpus/fingerprint.py`、`asr_lab/tests/test_corpus_fingerprint.py`

## 目标

为语料比较边界生成内容寻址标识，避免内容已经变化却继续沿用旧 `v1` 标签和旧指标。

## 核心概念

- 比较相关清单内容先序列化为键排序、无多余空白的 UTF-8 JSON，再计算 SHA-256。
- `created_at`、人工 `corpus_version` 标签和指纹字段自身不进入哈希；换标签不能伪装成内容变化。
- 样本音频摘要、参考原文、规范化结果、规范化版本、语言/场景标签和来源元数据均进入指纹。
- 实验比较边界由 `corpus_version + corpus_fingerprint` 共同表达。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m voice_asr_lab fingerprint-corpus-manifest asr_lab/corpus/manifests/voice-asr-eval-v1.json
python -m unittest discover -s asr_lab/tests -p 'test_corpus_fingerprint.py' -v
```

## 预期结果

保存的指纹与重新计算值一致；分别修改音频摘要、参考文本、场景标签和规范化版本时均生成不同内容指纹。

## 实际输出

```text
status=matched
corpus_version=v1
stored_fingerprint=corpus-sha256-46f7d367fe4b7605cdf2a0d8e4a76643b24aa911c5b49e889d0eb4df3472620b
matches=true

Ran 4 tests in 0.004s
OK
```

## 结果解释

清单现在可以自证其内容没有在保存指纹后被静默编辑。将来修改样本或规则时，旧指纹会立刻失配；维护者应创建新的人类版本标签并保存新指纹，而不是把新旧指标混合。

## 遇到的问题

若把 `corpus_version` 本身放入内容哈希，仅将 `v1` 改名为 `v2` 就会产生“新指纹”，但音频和参考答案完全相同。实现特意排除此字段，让指纹回答“内容是否变化”，让标签回答“我们如何命名这个发布版本”。

## 进入下一步的条件

- [x] v1 保存值与重新计算值一致。
- [x] 音频、参考文本、标签和规范化版本变化均有测试。
- [x] 时间戳和人工标签不会伪造内容变化。
- [x] JSON 键顺序不会影响结果。
- [x] 清单校验会拒绝陈旧指纹。
