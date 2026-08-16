# 检查点：独立 ASR 实验工程骨架

## 元数据

- `task_id`: `1.1`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `Windows 11 临时环境；Python 3.14.7；正式环境快照将在任务 1.3 建立`
- `evidence`: `asr_lab/pyproject.toml`、`asr_lab/src/voice_asr_lab/`、`asr_lab/tests/test_scaffold.py`

## 目标

建立一个能独立运行和测试的最小 Python 工程，并验证它不会启动 Gateway、数据库、网络连接或其他产品模块，为后续 ASR 实验提供干净边界。

## 核心概念

- **实验台与产品服务分离**：先单独解决 Runtime、模型和评测问题，避免把模型错误与 WebSocket、数据库错误混在一起。
- **src 布局**：Python 包位于 `src/` 下，测试必须显式从源码目录导入，降低意外导入仓库同名文件的风险。
- **无导入副作用**：导入包和运行最小入口只描述当前边界，不连接网络、不启动进程，也不加载模型。

## 入口命令

工作目录：`D:\workspace\ai\Voice\asr_lab\src`

```powershell
python -m voice_asr_lab
python -m unittest discover -s '..\tests' -v
```

## 预期结果

- CLI 返回 `stage=scaffold` 和空的 `services_started`。
- 项目运行依赖为空。
- 测试证明入口没有调用网络连接或子进程启动函数。

## 实际输出

```text
{
  "name": "voice-asr-lab",
  "version": "0.1.0",
  "stage": "scaffold",
  "purpose": "evaluate-local-asr-providers",
  "services_started": []
}

Ran 2 tests in 0.001s
OK
```

## 结果解释

工程已经具备最小包元数据、模块入口和标准库测试。空依赖列表与隔离性测试共同证明当前骨架没有引入产品服务或 ASR Runtime；它尚未证明任何真实 ASR 能力，这些能力必须在后续候选检查点中逐项验证。

## 遇到的问题

当前机器只发现 Python 3.14.7，而部分机器学习 Runtime 可能尚不支持该版本。公共骨架保持纯标准库；每个 ASR 候选将在自己的任务中选择并锁定兼容 Python 环境。

## 进入下一步的条件

- [x] `asr_lab` 可以作为 Python 模块运行。
- [x] CLI 明确报告没有启动任何服务。
- [x] 项目运行依赖列表为空。
- [x] 两个隔离性测试全部通过。
- [x] OpenSpec 任务 1.1 已勾选完成。

