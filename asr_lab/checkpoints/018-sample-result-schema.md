# 检查点：逐样本原始结果契约

## 元数据

- `task_id`: `3.1`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/schemas/sample-result.schema.json`、`asr_lab/schemas/sample-result.example.json`、`asr_lab/src/voice_asr_lab/experiment/sample_result.py`、`asr_lab/tests/test_sample_result.py`

## 目标

定义一条 ASR 样本执行完成后必须保留的原始事实，让不同 Provider 的结果都能关联到同一运行、环境、语料和资源采样，并在计算 CER、WER、RTF 等派生指标之前发现证据缺失或自相矛盾。

## 核心概念

- **原始事实与派生指标分层**：本 Schema 保存输入、原生输出、配置和时间事实，不保存 CER、WER、RTF 等可重新计算的指标，避免原始证据被统计逻辑污染。
- **引用而不是复制**：结果通过 `environment_snapshot_id`、语料指纹和资源采样 ID 连接其他证据，不重复嵌入整份环境快照或采样记录。
- **原生返回不失真**：`provider_payload` 接受任意 JSON 值，因为真实 Runtime 可能返回对象、列表、标量或 `null`；稳定文字单独放在统一字段中。
- **墙钟与单调时钟各司其职**：UTC 墙钟用于审计和跨文件阅读，单调纳秒用于计算推理与总耗时，避免系统时间调整影响持续时间。
- **结构校验加语义校验**：JSON Schema 约束字段和类型，Python 校验器继续检查时间顺序、耗时差值、成功/失败退出状态、错误对象、规范化版本和引用唯一性。
- **空文字不是错误**：静音、噪声等无语音样本成功时使用空字符串和空规范化版本；失败则保留可空文字与结构化错误，二者不会混淆。

## 入口命令

工作目录为仓库根目录 `D:\workspace\ai\Voice`。

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m voice_asr_lab validate-sample-result asr_lab/schemas/sample-result.example.json
python -m unittest asr_lab.tests.test_sample_result asr_lab.tests.test_cli_architecture -v
python -m unittest discover -s asr_lab/tests -v
```

## 预期结果

完整成功示例应覆盖环境、语料输入、Provider、模型、配置、原始及稳定文字、墙钟、单调时钟、退出状态和资源采样引用，并通过 CLI 校验。测试还应证明失败记录、无语音结果和非对象原生返回能够如实保存，同时拒绝缺字段、错误时间顺序、不一致耗时、非法退出状态和重复资源引用。

## 实际输出

```text
{
  "status": "valid",
  "result": "D:\\workspace\\ai\\Voice\\asr_lab\\schemas\\sample-result.example.json",
  "run_id": "run-20260816T120000000000Z-a1b2c3d4e5f6",
  "sample_id": "zh-short-command-001",
  "errors": []
}

Ran 15 tests in 0.013s
OK

Ran 103 tests in 2.363s
OK
```

## 结果解释

示例和定向测试证明，一条逐样本记录已经能完整表达“在哪个环境、用哪个模型和配置、处理哪个版本化输入、得到了什么原生及稳定文字、花了多久、如何退出、关联哪些资源采样”。全量回归证明这项契约没有破坏前两部分的环境和语料工具。

这一步只定义一次样本执行结束后的结果形状，并没有定义 partial、VAD endpoint、final 或取消过程中的事件顺序，也没有实际运行任何真实 ASR 模型。流式过程事实属于任务 3.2；计时器、合成 Provider 和指标计算分别在后续任务实现。

## 遇到的问题

初版把 `provider_payload` 限定为 JSON 对象，但 FunASR 等 Runtime 的原生返回可能是列表。为避免包装或改写原始证据，最终契约允许任意 JSON 形状，并添加列表返回的回归测试。另一个边界是 JSON Schema 不能表达所有跨字段关系，因此使用独立语义校验器补充成功状态、时间差值和规范化版本规则。

## 进入下一步的条件

- [x] Schema 覆盖任务要求的环境、模型、配置、文字、时间、错误、退出状态和资源采样引用。
- [x] 成功、失败、无语音和非对象 Provider 原生返回均有测试证据。
- [x] 跨字段时间、状态、错误和规范化规则能够拒绝矛盾记录。
- [x] CLI 提供可复制样例并输出机器可读校验结果。
- [x] 103 个全量测试通过，可以进入任务 3.2：流式事实事件 Schema。
