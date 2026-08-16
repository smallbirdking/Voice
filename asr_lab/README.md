# Voice ASR Lab

这是本仓库中独立的本地 ASR 实验工程。它先用于理解和比较各个 ASR Runtime，之后才为语音服务提供经过验证的 Provider 结论。

当前最小工程只使用 Python 标准库，不包含以下产品能力：

- FastAPI 或 WebSocket Gateway
- PostgreSQL 或其他数据库连接
- 录音、命令、设备、视觉和客户端模块
- ASR 模型下载、加载或推理

Python 实现位于 `src/voice_asr_lab`，按 `core`、`system`、`corpus` 三个职责目录组织；
目录边界和依赖方向见 [`src/voice_asr_lab/README.md`](src/voice_asr_lab/README.md)。顶层只保留
包元数据与 CLI 入口，后续 Provider 和实验工具不再继续堆叠为平级文件。

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

## 观察一次运行的记录关联

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab demo-run-linkage
```

该命令采集当前主机与 NVIDIA 快照，创建一次新的 `run_id`，并用规范化环境 JSON 的 SHA-256 创建
`environment_snapshot_id`。输出中的逐样本结果、资源采样和报告示例都携带这两个标识，因此后续即使文件分开保存，也能判断它们是否来自同一次运行和同一份环境快照。

## 验证本地网络边界

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab prepare-synthetic-cache
python -m voice_asr_lab offline-smoke
```

准备命令在被 Git 忽略的模型缓存中生成一个确定性小型标记；离线命令先按保留清单校验缓存，再阻断当前 Python 进程的非 loopback socket，并完全在本地处理合成 PCM。规则详见 [`NETWORK_POLICY.md`](NETWORK_POLICY.md) 和机器可读的 [`network-policy.json`](network-policy.json)。这个步骤只验证网络与缓存边界，不代表已经运行真实 ASR 推理。

## 保存环境基线

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab capture-baseline
```

命令把主机、NVIDIA、实验台版本、依赖锁文件摘要、网络与存储策略摘要以及 Git 状态合并为一份内容寻址的 JSON，默认独占保存到 `reports/baselines/environment-baseline-v1.json`。如果文件已存在，命令拒绝覆盖；需要记录新环境时应使用新的 `--output` 文件名。

## 验证语料清单契约

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab validate-corpus-manifest asr_lab/corpus/manifests/schema-example.json
```

清单 Schema 固定语料版本、稳定样本标识、相对音频路径与 SHA-256、媒体格式、时长、
语言、场景、原文、规范化文本、语言片段、规范化版本、内容指纹和来源许可。命令还检查
样本标识唯一、路径不能逃逸 `corpus/source`，重新计算文字规范化结果与内容指纹，并要求
静音和纯噪声样本使用空参考文本。示例不包含真实音频；实际 v1 清单包含 7 个受许可样本。

## 检查并预处理真实语料

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab check-corpus-audio asr_lab/corpus/manifests/voice-asr-eval-v1.json
python -m voice_asr_lab preprocess-corpus asr_lab/corpus/manifests/voice-asr-eval-v1.json --output-root asr_lab/corpus/derived/v1
```

第一条命令逐样本核对文件、摘要和 WAV 媒体属性。第二条命令使用版本化整数算法生成
16kHz、单声道、PCM16 派生输入；它拒绝覆盖源文件或任何已有输出。派生目录不进入 Git，
可随时从受版本控制的源语料重建。

## 验证语料版本并生成报告

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab fingerprint-corpus-manifest asr_lab/corpus/manifests/voice-asr-eval-v1.json
python -m voice_asr_lab report-corpus asr_lab/corpus/manifests/voice-asr-eval-v1.json `
  --derived-root asr_lab/corpus/derived/v1 `
  --output-json asr_lab/reports/corpus/voice-asr-eval-v1-summary.json `
  --output-markdown asr_lab/reports/corpus/voice-asr-eval-v1-summary.md
```

内容指纹覆盖音频摘要、参考文本、语言/场景标签和规范化版本。报告同时验证源文件与派生
输入，汇总中文、英文、混合、静音、噪声、长句、短命令覆盖，并保留许可证限制。报告命令
采用独占写入；需要重新发布时应使用新文件名，不能静默覆盖旧证据。

## 学习检查点

每个已完成任务都应在 `checkpoints/` 中留下可复盘记录。新记录从
[`checkpoints/TEMPLATE.md`](checkpoints/TEMPLATE.md) 复制，并按任务顺序命名，例如
`001-scaffold.md`。模板要求保存实际执行命令和输出证据，不能只写最终结论。
