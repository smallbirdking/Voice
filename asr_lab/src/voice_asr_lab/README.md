# `voice_asr_lab` 包结构

顶层只保留 Python 包元数据、`python -m voice_asr_lab` 入口和 CLI 编排。具体实现按职责分组：

```text
voice_asr_lab/
├── core/       # 通用 Schema 校验、运行与环境标识
├── system/     # 主机、NVIDIA、离线边界、环境基线
├── corpus/     # 语料资产、清单、校验、预处理、规范化、指纹、报告
├── cli.py      # 稳定命令行入口，只负责编排上述模块
├── __main__.py
└── __init__.py
```

依赖方向保持单向：`core` 不依赖其他业务目录；`system` 和 `corpus` 可以使用 `core`；
CLI 可以编排全部目录。`system` 与 `corpus` 不应互相依赖，这样后续 Provider 实验可以分别
复用环境事实和固定语料，而不会形成循环导入。
