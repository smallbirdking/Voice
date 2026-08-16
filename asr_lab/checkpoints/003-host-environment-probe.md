# 检查点：主机环境结构化探测

## 元数据

- `task_id`: `1.3`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `host-environment schema 1.0.0；Windows 11；CPython 3.14.7`
- `evidence`: `asr_lab/schemas/host-environment.schema.json`、`asr_lab/src/voice_asr_lab/environment.py`、`asr_lab/tests/test_environment.py`

## 目标

实现不依赖第三方包的主机探测，以版本化 JSON 记录操作系统、WSL2、CPU、内存、工作区磁盘和 Python，并用 Schema 测试防止字段缺失或类型漂移。

## 核心概念

- **环境快照**：ASR 性能结果只有绑定硬件、Runtime 和磁盘环境后才可比较。
- **未知不等于否定**：探测失败使用 `null` 或错误状态，不能把未知 WSL2 状态记录成未启用。
- **版本化 Schema**：消费者可以根据 `schema_version` 判断字段契约，测试会拒绝缺少必填部分的输出。
- **单调降级**：内存、磁盘或 WSL 单项失败时保留其他有效信息和错误证据。

## 入口命令

工作目录：`D:\workspace\ai\Voice\asr_lab\src`

```powershell
python -m voice_asr_lab probe-host
python -m unittest discover -s '..\tests' -v
```

## 预期结果

- CLI 输出满足 `host-environment` 1.0.0 Schema 的 JSON。
- 输出包含 Windows、WSL2、CPU、内存、工作区磁盘和 Python 六类信息。
- WSL 缺失、拒绝或超时时形成显式状态，不导致整个命令失败。
- Schema 校验能够识别缺失必填字段。

## 实际输出

```text
schema_version: 1.0.0
platform: Windows 11 / 10.0.26200 / AMD64 / 64bit
wsl: error / wsl2_detected=null
wsl details: 拒绝访问；Wsl/EnumerateDistros/Service/E_ACCESSDENIED
cpu: 24 logical cores / Intel64 Family 6 Model 198 Stepping 2
memory: 33567981568 total bytes / windows-global-memory-status
workspace disk: 701751431168 total bytes
python: CPython 3.14.7 / C:\Python314\python.exe / not a virtual environment
schema errors: none

Ran 9 tests in 0.057s
OK
```

## 结果解释

Windows、CPU、内存、磁盘和 Python 探测均产生了有效值，完整快照通过 1.0.0 Schema。`wsl.exe` 可以找到，但当前进程枚举发行版时被系统拒绝，因此 `wsl2_detected` 正确保持未知；这不会影响当前公共工具，却会在需要 WSL2 的 Provider 环境准备前成为待解决条件。

## 遇到的问题

WSL 的中文错误使用无 BOM 的 UTF-16LE，而 Windows 控制台默认输出编码不是 UTF-8，首次 JSON 显示出现乱码。探测器现已识别 UTF-16 输出，CLI 也会把最终 JSON 统一编码为 UTF-8；新增测试覆盖“拒绝访问”中文往返。

## 进入下一步的条件

- [x] 六类要求的主机信息都有固定字段。
- [x] 单项失败有明确状态、`null` 或错误说明。
- [x] CLI 输出通过版本化 Schema 校验。
- [x] 缺失必填字段会被校验测试拒绝。
- [x] Windows UTF-16 命令输出可以正确进入 UTF-8 JSON。
- [x] 全部九个测试通过。

