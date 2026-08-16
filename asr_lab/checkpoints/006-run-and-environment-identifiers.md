# 检查点：运行标识与环境快照关联

## 元数据

- `task_id`: `1.6`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `run identity schema 1.0.0；Windows host and NVIDIA snapshot`
- `evidence`: `asr_lab/src/voice_asr_lab/core/identifiers.py`、`asr_lab/schemas/run-context.schema.json`、`asr_lab/schemas/run-linked-record.schema.json`、`asr_lab/tests/test_identifiers.py`

## 目标

定义一次实验的 `run_id` 和它所使用的 `environment_snapshot_id`，让分别保存的逐样本结果、资源采样和汇总报告能够证明它们来自同一次执行及同一份精确环境快照，并能拒绝跨运行误拼接。

## 核心概念

`run_id` 标识一次执行，格式为 `run-<UTC 时间>-<12 位随机十六进制>`。UTC 时间便于人阅读和排序，48 位随机后缀避免同一微秒内创建多次运行时碰撞。它不依赖数据库或全局计数器，因此隔离的 Provider Runtime 都能创建运行。

`environment_snapshot_id` 使用 `env-sha256-<64 位摘要>`。计算前先把环境对象转换为键名排序、无多余空白的规范化 JSON，再计算 SHA-256。因此 JSON 字段顺序不同不会改变标识，任何被记录的环境内容变化都会改变标识。

环境摘要标识的是“某一份精确快照”，不是机器的永久身份。快照包含采集时间、可用内存、磁盘和空闲显存等动态字段，所以重新采集得到新 ID 是正确行为。横向实验引用相同的已保存快照 ID，才能说明它们使用了同一基线证据。

逐样本结果、资源采样和报告使用相同的最小关联信封：`record_type`、`run_id`、`environment_snapshot_id` 和 `payload`。本任务只定义公共关联字段，后续任务再分别定义三类 `payload` 的完整业务 Schema。

## 入口命令

在 `asr_lab/src` 运行一次真实关联演示：

```powershell
python -m voice_asr_lab demo-run-linkage
```

运行专项测试：

```powershell
python -m unittest discover -s '..\tests' -p 'test_identifiers.py' -v
```

运行完整测试：

```powershell
python -m unittest discover -s '..\tests' -v
```

## 预期结果

- 运行上下文和关联记录分别通过版本化 JSON Schema。
- 相同环境内容即使字典字段顺序不同，也产生相同环境摘要。
- 环境内容变化后产生不同环境摘要。
- 逐样本结果、资源采样和报告都携带同一个运行 ID 和环境快照 ID。
- 某条记录混入其他运行 ID、引用其他环境，或缺少三类证据之一时，关联校验返回明确错误。

## 实际输出

2026-08-16 的真实运行上下文为：

```json
{
  "run_id": "run-20260816T082534178136Z-b9d2568f2c31",
  "environment_snapshot_id": "env-sha256-b4925679bf1271ba5405bfc3450e42aad129a650ad6060839ea9685fade3ee31",
  "created_at": "2026-08-16T08:25:34.178136Z"
}
```

输出中的三类记录为：

```text
sample_result   -> run-20260816T082534178136Z-b9d2568f2c31 / env-sha256-b492...ee31
resource_sample -> run-20260816T082534178136Z-b9d2568f2c31 / env-sha256-b492...ee31
report          -> run-20260816T082534178136Z-b9d2568f2c31 / env-sha256-b492...ee31
linkage_errors  -> []
```

专项测试结果为 `Ran 7 tests ... OK`；完整回归结果为 `Ran 26 tests ... OK`。

## 结果解释

三类输出不需要位于同一个文件，也不需要依赖目录名猜测关系。只要读取公共信封，就能先按 `run_id` 聚合，再核对 `environment_snapshot_id`。这为以后把逐样本 JSONL、资源采样 JSONL 和 Markdown/JSON 报告分开保存提供了稳定连接键。

SHA-256 在这里用于内容寻址和误关联检测，不是用于隐藏敏感信息。原始环境快照仍须保存；只有摘要而没有快照内容，无法重现实验环境。

测试还故意把一个逐样本结果改成其他 `run_id`，并只提供这一类记录。验证器同时报告运行不匹配以及缺少资源采样和报告，说明错误不会被静默接受。

## 遇到的问题

现有轻量 Schema 校验器最初不支持 JSON Schema 的 `pattern` 关键字，无法校验两个标识的格式。本步加入了正则模式校验，并通过错误 `run_id` 测试证明规则生效。

如果仅使用采集时间生成运行 ID，两个进程可能在极短时间内冲突；因此增加随机后缀。测试可注入固定时间和后缀，既保持生产唯一性，也保持单元测试确定性。

## 进入下一步的条件

- 两类标识的生成规则、版本化 Schema 和格式校验已经实现。
- 环境摘要的顺序稳定性、内容敏感性均有确定性测试。
- 逐样本结果、资源采样和报告的同运行关联及跨运行拒绝均通过测试。
- 真实主机演示输出 `linkage_errors: []`，完整回归为 26/26 通过。
- 可以开始任务 1.7：固定允许下载模型但禁止向云端发送测试音频的本地网络边界。
