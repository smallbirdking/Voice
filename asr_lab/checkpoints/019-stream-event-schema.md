# 检查点：流式事实事件契约

## 元数据

- `task_id`: `3.2`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/schemas/stream-event.schema.json`、`asr_lab/schemas/stream-event.example.jsonl`、`asr_lab/src/voice_asr_lab/experiment/events.py`、`asr_lab/tests/test_stream_events.py`

## 目标

定义 Provider 无关、逐行保存且不可变的流式事实事件，使音频从进入实验台到会话关闭的原始过程可以重放、审计，并为后续延迟计算提供可靠时间点。

## 核心概念

- 每行 JSONL 是一条事实，修订中的 partial 追加新事件，不能覆盖旧文字。
- 公共关联字段把事件绑定到运行、环境、样本、Provider 和会话。
- `sequence` 描述记录顺序，`monotonic_ns` 描述持续时间顺序，两者都必须非倒退。
- 稳定 payload 形状保留通用字段；事件类型决定哪些字段必须非空。
- `provider_payload` 接受任意 JSON，保证原生信息不因统一字段而丢失。
- `cancelled` 是事实事件而不是关闭本身，之后仍必须出现唯一的 `closed`。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m voice_asr_lab validate-stream-events asr_lab/schemas/stream-event.example.jsonl
python -m unittest asr_lab.tests.test_stream_events asr_lab.tests.test_cli_architecture -v
```

## 预期结果

成功示例应覆盖音频进入、入队、开始消费、partial、VAD endpoint、提交、final 和关闭；取消路径由单元测试覆盖。验证器应拒绝断裂序号、倒退时间、跨会话混合、空 partial、缺少终结关闭和 JSONL 空行。

## 实际输出

```text
status=valid
event_count=8
event_types=audio_received,enqueued,consumption_started,partial,vad_endpoint,segment_committed,final,closed
errors=[]

Ran 12 tests in 0.014s
OK
```

## 结果解释

事件层现在能无损表达任务列出的九类事实，并且成功与取消两条生命周期都有测试。它只保存原始时间点和状态，不在此处计算 partial、final、排队或推理延迟；这些派生定义由任务 3.3 的计时工具负责。

## 遇到的问题

一个成功会话不应同时制造 `cancelled` 事件，因此保留的成功示例只含八类事件，取消由独立测试流证明。这样既覆盖 Schema 能力，也不产生语义矛盾的演示记录。

## 进入下一步的条件

- [x] 九类要求事件全部进入版本化枚举和字段契约。
- [x] 成功事件流通过结构、关联、顺序、时间和关闭校验。
- [x] 取消事件必须由关闭收尾，并有确定性测试。
- [x] CLI 输出机器可读结果并包含可复制样例。
- [x] 可以进入任务 3.3：基于这些事实时间点计算统一延迟。
