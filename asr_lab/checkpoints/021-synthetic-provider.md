# 检查点：确定性合成 Provider

## 元数据

- `task_id`: `3.4`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/experiment/synthetic_provider.py`、`asr_lab/tests/test_synthetic_provider.py`

## 目标

实现一个不加载真实模型、却能稳定产生流式过程的测试 Provider，用它隔离验证事件、计时、失败和取消管线本身。

## 核心概念

- 合成 Provider 的目标不是模拟准确率，而是提供可配置、可重复的管线输入。
- partial 文字、final 文字、排队延迟、partial 间隔、endpoint 延迟和 final 延迟均由配置显式给出。
- 手动时钟直接前进，不依赖操作系统调度，因此重复运行得到完全相同事件。
- 失败和取消都保留结构化结果，并以 `cancelled` 后接 `closed` 完成事件生命周期。
- 失败与取消配置互斥，非法延迟和越界 partial 数在运行前拒绝。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m unittest asr_lab.tests.test_synthetic_provider asr_lab.tests.test_timing -v
```

## 预期结果

成功配置应产生两个 partial、稳定 final 和有效关闭，延迟精确为排队 2ms、首 partial 12ms、final 8ms。失败应携带结构化错误；取消应在指定 partial 后停止且不产生 final。

## 实际输出

```text
success_events_are_identical=true
queue_latency_ms=[2.0]
first_partial_latency_ms=12.0
final_latency_ms=8.0
failure_status=failed, terminal=cancelled -> closed
cancellation_partial_count=1, final_count=0

Ran 8 tests in 0.003s
OK
```

## 结果解释

结果证明后续实验管线可以先用确定事实验证，而不把模型下载、GPU、Runtime 或识别波动混进工具本身。它没有证明任何真实 ASR 能力，所有 `synthetic` 结果必须明确与原生候选分开。

## 遇到的问题

事件契约没有独立 `failure` 类型，因为失败的完整结构已经属于逐样本 outcome。流式层记录失败触发的取消和关闭事实，逐样本层保存错误类型、阶段、代码与可重试性，从而避免两处错误模型发生漂移。

## 进入下一步的条件

- [x] 成功、失败和取消三条路径都有确定性测试。
- [x] 配置延迟与统一计时工具计算结果一致。
- [x] 所有产生的事件流均通过任务 3.2 契约。
- [x] 可以进入任务 3.5：让真实音频文件按离线或真实时间节奏进入 Provider。
