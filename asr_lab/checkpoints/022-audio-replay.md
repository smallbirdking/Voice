# 检查点：离线输入与单路真实时间回放

## 元数据

- `task_id`: `3.5`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/experiment/replay.py`、`asr_lab/tests/test_replay.py`

## 目标

从本地 PCM WAV 无损读取音频，并以离线或单路真实时间两种模式切块送入下游，验证回放节奏、累计音频位置和媒体时长一致。

## 核心概念

- 文件输入保留原始 PCM 字节，不执行隐藏重采样或声道转换。
- 块大小按帧而不是按裸字节计算，声道和采样宽度不会破坏边界。
- 离线模式尽快发出所有块，适合纯推理吞吐实验。
- 真实时间模式在音频块可用前等待该块的实际时长，模拟采集节奏。
- 最后一块通常不足配置块长，必须按实际帧数等待，不能凭配置补齐时间。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m unittest asr_lab.tests.test_replay asr_lab.tests.test_synthetic_provider -v
```

## 预期结果

250ms 的 16kHz PCM16 单声道测试音频按 100ms 切块后应得到 100、100、50ms 三块；真实时间可用点应为 100、200、250ms，离线模式总耗时为 0，拼接后字节与输入完全一致。

## 实际输出

```text
chunk_duration_ms=[100.0, 100.0, 50.0]
audio_offset_ms=[100.0, 200.0, 250.0]
realtime_elapsed_ms=250.0
offline_elapsed_ms=0.0
pcm_round_trip=true

Ran 8 tests in 0.008s
OK
```

## 结果解释

真实时间节奏由同一个可注入时钟控制，因此测试不需要真的等待 250ms，后续正式运行换成系统时钟即可得到相同语义。回放器当前是单流顺序组件，并发调度属于后面的容量基准，不在这一小步提前实现。

## 遇到的问题

“每 100ms 发块”不能理解成最后一块也等待 100ms，否则 250ms 音频会错误报告成 300ms。实现使用实际帧数计算每块时长，测试明确锁定这个边界。

## 进入下一步的条件

- [x] PCM WAV 输入的格式、字节和时长可核对。
- [x] 离线与真实时间模式发出完全相同的音频块。
- [x] 真实时间节奏与累计音频位置精确对齐。
- [x] 可以进入任务 3.6：在推理期间独立采集资源事实。
