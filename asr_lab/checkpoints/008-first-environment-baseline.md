# 检查点：第一份环境基线

## 元数据

- `task_id`: `1.8`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `environment baseline schema 1.0.0；env-sha256-7699e9ce...dbb81`
- `evidence`: `asr_lab/reports/baselines/environment-baseline-v1.json`、`asr_lab/reports/baselines/environment-baseline-v1.md`、`asr_lab/src/voice_asr_lab/system/baseline.py`、`asr_lab/tests/test_baseline.py`

## 目标

运行一个统一入口，把前面建立的主机探测、NVIDIA 探测、环境标识、依赖锁、网络策略、存储策略和源码状态合并为第一份不可覆盖、机器可读的环境基线，并配套学习说明。完成这一步后，后续语料和 Provider 结果才有明确的环境引用起点。

## 核心概念

环境基线不是一串手工抄写的硬件名称。它是一个通过版本化 JSON Schema 校验的完整对象，并包含其依赖锁文件、策略文件和源码状态。`environment_snapshot_id` 对除自身以外的全部字段计算规范化 JSON SHA-256，所以任何内容变化都会被验证器发现。

“基线”也不等于永久不变。可用内存、磁盘、空闲显存、驱动、依赖和源码都会变化。第一份基线作为历史证据保留；需要新环境时创建新文件和新 ID，不能覆盖旧文件。

`source_dirty: true` 不是校验失败，它忠实说明采集时工作树含有未提交内容。正式横向性能测试应从已审阅提交重新采集并尽量获得 `source_dirty: false`，但不能为了好看而修改这份历史记录。

## 入口命令

在 `asr_lab/src` 目录保存默认第一份基线：

```powershell
python -m voice_asr_lab capture-baseline
```

校验已保存 JSON：

```powershell
python -c "import json; from pathlib import Path; from voice_asr_lab.system.baseline import validate_environment_baseline; p=Path('../reports/baselines/environment-baseline-v1.json'); print(validate_environment_baseline(json.loads(p.read_text(encoding='utf-8'))))"
```

运行专项和完整测试：

```powershell
python -m unittest discover -s '..\tests' -p 'test_baseline.py' -v
python -m unittest discover -s '..\tests' -v
```

## 预期结果

- 基线包含主机、WSL、CPU、内存、磁盘、Python、GPU、驱动、CUDA 可见性、实验台版本、依赖锁摘要、策略摘要和 Git 状态。
- 嵌套的主机及 NVIDIA 结果继续通过各自 Schema。
- 整体基线通过 `environment-baseline.schema.json`，且内容重新计算得到相同 ID。
- 默认命令独占创建 `environment-baseline-v1.json`，再次执行时拒绝覆盖。
- 学习说明引用相同环境 ID，并解释动态字段、已知限制和后续使用方式。

## 实际输出

真实保存摘要：

```json
{
  "status": "saved",
  "environment_snapshot_id": "env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81",
  "output": "D:\\workspace\\ai\\Voice\\asr_lab\\reports\\baselines\\environment-baseline-v1.json",
  "source_commit": "1b857a3c9676aae56f1a016aa2a1230255304c91",
  "source_dirty": true,
  "probe_errors": []
}
```

磁盘文件重新加载并校验得到：

```json
{
  "environment_snapshot_id": "env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81",
  "validation_errors": []
}
```

关键硬件为 Windows 11 build 10.0.26200、24 逻辑核、33,567,981,568 字节内存、NVIDIA GeForce RTX 5060 Ti 16,311 MiB、驱动 596.36、驱动兼容 CUDA 13.2。WSL2 可见，系统级 CUDA Toolkit 未安装。

## 结果解释

这份 JSON 可以成为后续结果中的 `environment_snapshot_id` 引用目标。报告不需要重复复制全部硬件字段，只需保存 ID；复盘时再通过 ID 找到完整快照。策略和锁文件摘要也进入内容地址，因此修改网络边界或依赖后不能继续冒用旧环境 ID。

采集时能够枚举到停止状态的 WSL2 `docker-desktop`，说明 WSL 功能存在，但没有证明 FunASR 等候选已经具备可用 Linux 环境。Python 3.14.7 是系统解释器且不是虚拟环境，后续每个候选仍必须建立独立、版本锁定的 Runtime。

驱动报告 CUDA 13.2，但 `nvcc` 不存在。这个基线只陈述驱动与 Toolkit 的区别；是否能在 GPU 上执行 PyTorch、ONNX Runtime 或 CTranslate2，必须由对应候选的真实最小加载和推理验证。

## 遇到的问题

普通受管终端完成了采集与校验，但在向保留报告目录创建 JSON 时被文件写入沙箱拒绝。确认目标文件不存在后，使用一次精确授权执行相同命令，成功独占创建文件。获准运行还能枚举 WSL2，而早期受限探测曾得到访问拒绝；学习报告因此明确提醒后续记录实际 Runtime 的执行上下文。

第一次用于展示文件内容的 PowerShell 命令在 `asr_lab/src` 下多写了一层相对路径，导致展示失败；同一命令中的 Python 重新校验使用正确路径并成功。随后使用正确的 `../reports/baselines/...` 路径读取了全部关键字段。

## 进入下一步的条件

- 第一份机器可读环境基线已保存且不会被默认命令覆盖。
- JSON Schema、嵌套探测 Schema 和内容摘要重新计算均通过。
- 学习说明引用相同环境 ID，并记录 WSL、CUDA、源码脏状态和动态资源限制。
- 后续实验已经有统一的环境引用目标，可以在下一步开始任务 2.1：定义版本化语料清单 Schema。
