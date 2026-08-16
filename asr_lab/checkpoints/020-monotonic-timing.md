# 检查点：单调时钟与延迟边界

## 元数据

- `task_id`: `3.3`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/experiment/timing.py`、`asr_lab/tests/test_timing.py`、`asr_lab/schemas/stream-event.example.jsonl`

## 目标

实现统一单调计时工具并固定首个 partial、final、排队和推理耗时的起止点，使后续 Provider 不会各自选择有利的延迟定义。

## 核心概念

- 系统时钟只负责可审计 UTC 时间，持续时间只使用单调纳秒。
- `ManualClock` 由测试显式推进，无需真实等待即可得到确定延迟。
- 首个 partial 从首块音频进入到第一个非空 partial。
- final 从同段 VAD endpoint 开始；没有 endpoint 时从显式提交开始。
- 排队从 `enqueued` 到同一音频块的 `consumption_started`。
- 合成流程中的推理边界从首次开始消费到最后 stable final。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m unittest asr_lab.tests.test_timing asr_lab.tests.test_stream_events -v
```

## 预期结果

手工设置的时间点应精确产生 50.0ms partial、20.0ms final、0.1ms 排队和 219.8ms 推理耗时；无 VAD 时 final 应改用提交点，时钟倒退和重复标记应被拒绝。

## 实际输出

```text
first_partial_latency_ms=50.0
final_latency_ms=20.0
queue_latency_ms=[0.1]
inference_duration_ms=219.8
commit_only_final_latency_ms=19.9

Ran 10 tests in 0.009s
OK
```

## 结果解释

所有持续时间都能由保留事件的单调纳秒重新计算，墙钟变化不会影响结果。真实 Provider 可以使用 `SystemClock`，合成 Provider 和测试可以注入 `ManualClock`，二者遵守同一接口与边界。

## 遇到的问题

VAD endpoint 和段提交可能同时存在。统一规则优先使用 endpoint，因为它对应用户停止说话；只有 Provider 没有 VAD 事实时才使用显式提交，避免把实验台内部提交开销从 final 延迟中隐藏掉。

## 进入下一步的条件

- [x] 真实与手动时钟共享同一最小接口。
- [x] 时间倒退、重复标记和未知标记均被拒绝。
- [x] 四类耗时的起止点具有精确单元测试。
- [x] 可以进入任务 3.4：用手动时钟驱动确定性合成 Provider。
