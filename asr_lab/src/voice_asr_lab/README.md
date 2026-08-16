# `voice_asr_lab` 包结构

顶层只保留 Python 包元数据、`python -m voice_asr_lab` 入口和 CLI 编排。具体实现按职责分组：

```text
voice_asr_lab/
├── core/       # 通用 Schema 校验、运行与环境标识
├── system/     # 主机、NVIDIA、离线边界、环境基线
├── corpus/     # 语料资产、清单、校验、预处理、规范化、指纹、报告
├── experiment/ # 逐样本结果、事件、计时、回放、指标与聚合报告
├── commands/   # Command、Registry 和按领域组织的 CLI 处理器
├── cli.py      # 稳定组合根，只负责解析、分派和统一 JSON 输出
├── __main__.py
└── __init__.py
```

依赖方向保持单向：`core` 不依赖其他业务目录；`system` 和 `corpus` 可以使用 `core`；
`commands` 可以编排各领域，CLI 只依赖注册表。`system`、`corpus` 与 `experiment` 通过稳定标识和
Schema 交换事实，不直接形成循环依赖。这样后续 Provider 实验可以分别
复用环境事实和固定语料，而不会形成循环导入。
