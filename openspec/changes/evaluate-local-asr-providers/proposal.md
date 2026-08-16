## Why

现有实时语音服务计划直接把 FunASR 作为首个实现，但尚未用同一语料、硬件和指标验证其他本地候选，过早固化 Provider 契约可能掩盖各 Runtime 的真实差异。需要先以可学习、可复现的小步实验依次验证全部候选，再用数据决定主实时 ASR、备选方案和可能的二次校正角色。

## What Changes

- 建立独立于 Gateway、数据库、命令和客户端的本地 ASR 实验台，以及版本化的中文、英文、中英混合、静音、噪声、长句和短命令语料。
- 按固定顺序分别完成 FunASR、sherpa-onnx、faster-whisper 和 NVIDIA Parakeet/NIM 的原生最小实验；Parakeet 直接 Runtime 与 NIM 服务路径在条件允许时分别记录。
- 对每个候选记录可安装性、语言覆盖、原生流式能力、VAD、热词、partial/final 语义、准确率、延迟、吞吐、稳定性和资源占用；能力或部署门槛不满足时保留可审计的退出结论。
- 在完成原生实验后再定义统一 ASR Provider 契约，为可用候选建立适配器，并明确区分原生流式、分段推理和二次校正能力。
- 使用同一基准环境执行 1 路功能测试、5 路 SLA 测试和 10 路容量测试，产出可机器读取的原始结果与便于学习复盘的比较报告。
- 形成选型决策，分别确定主实时 Provider、可选回退 Provider、句末或录音二次校正方案以及暂不采用方案；完成该决策后才继续 `add-local-realtime-voice-service` 的其他模块。
- 保持 OpenAI 云端转写不在本变更范围内，不训练或微调模型，也不实现 Gateway、持久化、命令、设备或界面功能。

## Capabilities

### New Capabilities

- `asr-provider-evaluation`: 规定本地 ASR 候选的顺序化实验、统一语料与结果格式、能力门槛、公平基准、选型报告及进入后续语音服务实施的完成条件。

### Modified Capabilities

无。

## Impact

- 后续实施将新增隔离的 ASR 实验代码、Provider 原生示例、统一适配层、版本化测试语料、基准工具和实验报告，不新增对外网络 API。
- 将引入各候选的独立 Python、C++、ONNX、CUDA 或容器依赖以及本地模型文件；不同 Runtime 必须隔离和锁定版本，避免依赖互相污染。
- 会使用基准机器的 CPU、GPU、显存、内存和磁盘，但音频不得发送到外部云服务。
- `add-local-realtime-voice-service` 保持独立变更；其中 Gateway、存储、命令、设备和客户端任务应等待本变更产出选型决策后再继续，其 ASR 相关计划随后按结论更新。
