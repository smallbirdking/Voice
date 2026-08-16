# 检查点：失败可保留的资源采样

## 元数据

- `task_id`: `3.6`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/schemas/resource-sample.schema.json`、`asr_lab/src/voice_asr_lab/experiment/resources.py`、`asr_lab/tests/test_resources.py`

## 目标

在不影响 Provider 推理的前提下采集进程 CPU 时间、CPU 区间占用率、进程常驻内存和可用 NVIDIA GPU 指标，并把采集失败作为结果证据保存。

## 核心概念

- 每条采样具有稳定 ID、顺序、运行/环境/会话/样本关联和单调时间。
- CPU 百分比来自相邻采样的进程 CPU 时间差除以单调时间差，首条采样没有百分比。
- 进程内存记录 RSS：Windows 使用工作集，Linux 优先读取 `/proc/self/statm`。
- GPU 通过本地 `nvidia-smi` 读取利用率和显存；没有工具是 `unavailable`，执行失败是 `error`。
- 所有探针异常被转换成 `errors`，字段保留为 `null`，采样调用本身继续返回。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m unittest asr_lab.tests.test_resources asr_lab.tests.test_replay -v
```

## 预期结果

100ms 间隔内增加 30ms 进程 CPU 时间应得到 30%；内存和 GPU 字段通过 Schema。模拟 CPU 与 GPU 探针同时失败时，采样仍应返回有效记录，并分别保留两个错误原因。

## 实际输出

```text
first_cpu_percent=null
second_cpu_percent=30.0
memory_rss_bytes=12000
resource_sample_id=resource-sample-000002
failure_collectors=[process,gpu]
missing_nvidia_status=unavailable

Ran 7 tests in 0.007s
OK
```

## 结果解释

资源事实现在可以独立写入 JSONL，再由逐样本结果中的 `resource_sample_refs` 引用。采集权限或 GPU 工具问题不会伪装成零用量，也不会让一次有效推理变成失败。

## 遇到的问题

纯标准库没有统一的跨平台 RSS API，因此实现按平台选择系统原生来源，并把任何异常保留为采样错误。CPU 百分比可能在多核计算时超过 100%，实现不做错误截断。

## 进入下一步的条件

- [x] CPU、RSS 与可用 GPU 字段具有版本化 Schema。
- [x] 相邻采样 CPU 百分比使用单调时间确定性计算。
- [x] 缺少 GPU 和探针失败不会中断调用。
- [x] 可以进入任务 3.7：从原始文字、时间和样本语义计算派生指标。
