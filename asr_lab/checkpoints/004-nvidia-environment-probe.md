# NVIDIA 环境探测

## 元数据

- `task_id`: `1.4`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `NVIDIA GeForce RTX 5060 Ti；driver 596.36；driver-supported CUDA 13.2`
- `evidence`: `asr_lab/schemas/nvidia-environment.schema.json`、`asr_lab/src/voice_asr_lab/system/nvidia.py`、`asr_lab/tests/test_nvidia.py`

## 目标

用一个不会因为缺少 NVIDIA GPU、驱动或 CUDA Toolkit 而崩溃的命令，记录 GPU 型号、显存、驱动版本、CUDA 可见性和失败原因，为后续逐个测试 ASR 方案提供统一的硬件基线。

## 核心概念

`nvidia-smi` 来自 NVIDIA 驱动，它能说明操作系统是否看得到 NVIDIA GPU。它显示的 `CUDA Version` 是当前驱动支持的最高 CUDA 兼容版本，不等于本机已经安装同版本 CUDA Toolkit。

`nvcc` 是 CUDA Toolkit 的编译器。本机找不到 `nvcc`，只代表没有发现系统级 Toolkit；很多 Python 推理框架会自带所需 CUDA 运行库，所以这还不能判定后续 GPU 推理不可用。每个 ASR 方案仍需在自己的隔离环境里实际验证。

`CUDA_VISIBLE_DEVICES` 未设置时记录为 `null`，表示当前进程没有通过这个环境变量显式屏蔽或重排 GPU。

## 入口命令

在 `asr_lab/src` 目录执行：

```powershell
python -m voice_asr_lab probe-nvidia
```

运行相关自动化测试：

```powershell
python -m unittest discover -s '..\tests' -v
```

## 预期结果

- 有可用 NVIDIA GPU 时，状态为 `available`，并列出每张卡的型号、总显存、空闲显存和驱动版本。
- 没有 `nvidia-smi` 时，仍输出符合 JSON Schema 的结果，状态为 `not-installed`，GPU 数量为 0，并记录原因。
- 命令超时、返回错误或产生无法解析的内容时，不抛出未处理异常，而是在 `status` 和 `errors` 中留下可诊断信息。
- CUDA 驱动兼容版本和 CUDA Toolkit 安装状态分开记录。

## 实际输出

2026-08-16 在当前主机采集到：

```json
{
  "status": "available",
  "nvidia_smi": {
    "executable": "C:\\WINDOWS\\system32\\nvidia-smi.exe",
    "return_code": 0,
    "driver_supported_cuda_version": "13.2"
  },
  "visibility": {
    "nvidia_smi_visible": true,
    "cuda_visible_devices": null,
    "gpu_count": 1
  },
  "cuda": {
    "toolkit": {
      "status": "not-installed",
      "executable": null,
      "version": null,
      "details": "nvcc was not found on PATH or under CUDA_PATH."
    }
  },
  "gpus": [
    {
      "index": 0,
      "name": "NVIDIA GeForce RTX 5060 Ti",
      "driver_version": "596.36",
      "memory_total_mib": 16311,
      "memory_free_mib": 15021
    }
  ],
  "errors": []
}
```

完整测试结果为 `Ran 15 tests ... OK`。

## 结果解释

当前 Windows 主机能够通过驱动看到 1 张 NVIDIA GeForce RTX 5060 Ti，总显存约 15.93 GiB。采集时空闲显存为 15021 MiB；空闲值会随其他程序占用而变化，因此后续性能对比应在每次运行前重新采集。

驱动版本 596.36 报告最高兼容 CUDA 13.2。系统级 CUDA Toolkit 未被发现，但这一点不会阻止我们继续测试自带 CUDA 运行库的 ASR Python 包。真正能否使用 GPU，要由后续每个方案的框架探测和一次真实转写共同确认。

自动化测试还模拟了没有 `nvidia-smi` 和查询超时的机器，确认探测器会产生结构化失败结果，而不会使整个评测流程中断。

## 遇到的问题

当前没有发现系统级 `nvcc`。这不是本步骤的失败，因为本步骤的职责是如实探测并区分“驱动可见”和“Toolkit 已安装”。后续安装具体 ASR 方案时，应优先遵循该方案与 Python 3.14、PyTorch/CTranslate2 和 CUDA 运行时的实际兼容要求，而不是仅依据 `nvidia-smi` 顶部显示的 CUDA 数字选择包。

## 进入下一步的条件

- NVIDIA 探测结果通过版本化 JSON Schema 校验。
- 当前机器的 GPU、显存、驱动和 CUDA 状态已经留档。
- 无 GPU、命令超时和正常 GPU 三类分支均有自动化测试。
- 可以开始任务 1.5：建立模型、数据集、输出和日志目录，并设置忽略规则。
