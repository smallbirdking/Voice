# CLI 设计

`voice_asr_lab.cli` 是组合根，只负责创建注册表、解析参数、分派和输出 JSON。业务命令分成：

- `scaffold.py`：无副作用的默认说明命令。
- `system.py`：主机、GPU、离线边界和环境基线。
- `corpus.py`：语料清单、音频检查、预处理、指纹与报告。

## 使用的模式

### Command

每个 `CommandDefinition` 组合稳定命令名、帮助文字、参数配置函数和处理器。处理器是可以单独
测试和替换的执行策略，不直接打印或退出进程。

### Registry

`CommandRegistry` 是命令目录和分派器。新增命令时把定义加入对应领域的命令元组，不需要修改
`cli.py` 的控制流。注册表拒绝重复名字，避免后注册的命令静默覆盖已有行为。

### Result Object

所有处理器返回 `CommandResult(payload, exit_code)`。成功和失败都携带机器可读 JSON；入口根据
退出码统一选择 stdout 或 stderr。这样异常到 CLI 契约的转换留在领域命令中，输出机制只有一份。

## 新增命令

1. 在最接近的领域模块中实现参数配置函数和处理器。
2. 创建一个 `CommandDefinition` 并加入该模块的命令元组。
3. 为参数、成功结果、错误结果和退出码增加测试。
4. 只有出现新领域时才在 `commands/__init__.py` 注册新的命令组。

每个 `CommandDefinition` 必须提供至少一个 `examples`。注册表会拒绝没有样例的命令，架构测试
还会验证每条样例包含对应命令名，并确实出现在子命令帮助中。

开发环境先设置源码路径，然后查看任一命令的专属样例：

```powershell
$env:PYTHONPATH = "asr_lab/src"
python -m voice_asr_lab preprocess-corpus --help
```
