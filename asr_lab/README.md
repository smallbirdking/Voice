# Voice ASR Lab

这是本仓库中独立的本地 ASR 实验工程。它先用于理解和比较各个 ASR Runtime，之后才为语音服务提供经过验证的 Provider 结论。

当前最小工程只使用 Python 标准库，不包含以下产品能力：

- FastAPI 或 WebSocket Gateway
- PostgreSQL 或其他数据库连接
- 录音、命令、设备、视觉和客户端模块
- ASR 模型下载、加载或推理

## 运行最小入口

在仓库根目录执行：

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab
```

入口只输出工程名称、版本、当前阶段和边界声明，不监听端口、不连接数据库，也不启动子进程。

## 探测主机环境

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab probe-host
```

该命令以 JSON 输出 Windows 或其他主机平台、WSL2 可见性、CPU、内存、工作区磁盘和 Python 信息。输出在打印前会根据 `schemas/host-environment.schema.json` 校验；单个探测失败时会保留明确状态或错误，不会把未知信息伪装成零值。

## 探测 NVIDIA 与 CUDA 可见性

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab probe-nvidia
```

该命令分别记录 `nvidia-smi` 可见的 GPU、总显存与空闲显存、驱动版本、驱动报告的 CUDA 兼容版本、`CUDA_VISIBLE_DEVICES` 和本机 CUDA Toolkit（`nvcc`）。驱动可用不代表 Toolkit 已安装；没有 NVIDIA GPU 或命令失败时也会生成符合 `schemas/nvidia-environment.schema.json` 的结果。

## 运行隔离性测试

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m unittest discover -s asr_lab/tests -v
```

后续环境探测、语料、原生 Provider 实验、统一适配和基准工具会按 OpenSpec 任务逐步加入。

## 实验资产目录

目录的保留策略由 [`storage-layout.json`](storage-layout.json) 定义，并在
[`STORAGE.md`](STORAGE.md) 中解释。简要规则如下：

- `models/cache/`：下载的模型文件，本机缓存，不进入 Git。
- `models/manifests/`：模型标识、来源和摘要，作为复现证据保留。
- `corpus/source/` 与 `corpus/manifests/`：获得许可的原始语料及清单，允许版本控制。
- `corpus/derived/`：可重复生成的预处理音频，不进入 Git。
- `tmp/` 与 `logs/`：临时结果和运行日志，不进入 Git。
- `reports/`：需要长期保留的 JSON、JSONL 和 Markdown 实验报告，允许版本控制。

`tests/test_storage_layout.py` 会调用 `git check-ignore`，防止后续修改忽略规则时意外放开模型缓存或临时产物。

## 学习检查点

每个已完成任务都应在 `checkpoints/` 中留下可复盘记录。新记录从
[`checkpoints/TEMPLATE.md`](checkpoints/TEMPLATE.md) 复制，并按任务顺序命名，例如
`001-scaffold.md`。模板要求保存实际执行命令和输出证据，不能只写最终结论。
