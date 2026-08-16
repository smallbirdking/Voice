# 检查点：中英混合规范化与片段标注

## 元数据

- `task_id`: `2.7`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/corpus/text_normalization.py`、`asr_lab/src/voice_asr_lab/corpus/manifest.py`、`asr_lab/tests/test_mixed_normalization.py`

## 目标

让中英混合样本同时保留可审计原文、整体评分输入和分语言统计输入，并将三者的一致性纳入清单校验。

## 核心概念

- 原文永久保留，不用规范化结果覆盖它。
- 每个语言片段保存 `language`、`original`、`normalized`、`start` 和 `end`。
- 中性字符（空白与标点）跟随前一语言片段；整体规范化结果用一个空格连接各非空片段结果。
- 单语言样本同样记录一个完整片段，静音和噪声记录空片段数组。
- 校验器按 `text-normalization-v1` 重新计算结果并精确比较，陈旧结果或错误区间会使清单无效。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m unittest discover -s asr_lab/tests -p 'test_mixed_normalization.py' -v
python -m unittest discover -s asr_lab/tests -p 'test_corpus_manifest.py' -v
python -m voice_asr_lab validate-corpus-manifest asr_lab/corpus/manifests/voice-asr-eval-v1.json
```

## 预期结果

混合样本同时包含 zh 和 en 片段，片段原文按区间可从完整原文还原，整体与分段规范化结果匹配同一规则版本。

## 实际输出

```text
Mixed normalization: Ran 4 tests, OK
Corpus manifest:     Ran 11 tests, OK
validate-corpus-manifest:
  status=valid
  sample_count=7
  errors=[]
```

## 结果解释

真实混合样本规范化为 `请举起你的左手 please respond`，包含 `[0, 9)` 的中文片段和 `[9, 24)` 的英文片段。后续可对整体计算混合错误率，也可分别抽出中英文片段统计。

## 遇到的问题

首次人工填写中文长句片段时把结束索引误写成 43，实际长度为 40。新增的一致性校验立即报告 `language_segments` 不匹配；修正索引后清单恢复有效。这说明片段数据不能只靠 Schema 的类型检查。

## 进入下一步的条件

- [x] 原文、整体规范化文本和语言片段同时保留。
- [x] 真实混合样本同时包含 zh 和 en 统计输入。
- [x] 片段字符区间能够还原对应原文。
- [x] 单语言与非语音样本也有明确片段契约。
- [x] 陈旧规范化结果和错误片段索引会被校验拒绝。
