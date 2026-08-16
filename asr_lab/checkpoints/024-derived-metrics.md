# 检查点：可手工核对的 ASR 指标

## 元数据

- `task_id`: `3.7`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/experiment/metrics.py`、`asr_lab/tests/test_metrics.py`

## 目标

从已保存的规范化参考、识别文字和时间事实计算中文 CER、英文 WER、中英混合错误、关键词命中、静音误识别和实时率，并用无需模型即可手算的样例验证。

## 核心概念

- Levenshtein 距离同时保留替换、删除和插入数量，错误率分母始终是参考单元数。
- 中文 CER 忽略空白后按 Unicode 字符计数。
- 英文 WER 假定输入已经按版本化规则规范化，使用空白分词。
- 混合指标把每个汉字和每个拉丁词作为一个单元，避免用纯字符率惩罚英文长词。
- 关键词按单元序列匹配，`and` 不会误命中 `hand`。
- 静音/噪声样本单独报告是否出现任何非空白文字；实时率为推理毫秒除以音频毫秒。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m unittest asr_lab.tests.test_metrics -v
```

## 预期结果

“你好世界”到“你好世”为一次删除、CER 0.25；四词英文发生两个编辑时 WER 0.5；四个混合单元发生一次替换时为 0.25；500ms 推理处理 2000ms 音频时 RTF 为 0.25。

## 实际输出

```text
cer: distance=1, deletions=1, rate=0.25
wer: distance=2, reference_units=4, rate=0.5
mixed_error: distance=1, reference_units=4, rate=0.25
keyword_hits: 2/3, accidental_substring=false
silence_false_recognition=true
realtime_factor=0.25

Ran 6 tests in 0.000s
OK
```

## 结果解释

指标算法是纯函数，任何报告都能从原始结果重新生成。语言和场景决定适用指标；不适用项使用 `null`，不会用零冒充“完美识别”。空参考的编辑距离仍可保存，但错误率没有合法分母，因此为 `null`。

## 遇到的问题

中英混合不能直接套用中文字符率或英文空格分词。当前规则明确选择“汉字字符 + 拉丁词”，并依赖任务 2.7 保存的规范化版本；将来规则变化必须发布新版本，不能覆盖旧指标语义。

## 进入下一步的条件

- [x] 六类任务指标均由独立、无副作用函数实现。
- [x] 编辑距离、分母和编辑分类均可由小样例核对。
- [x] 不适用与无合法分母不会伪装成零错误率。
- [x] 可以进入任务 3.8：聚合逐样本结果并保留失败项。
