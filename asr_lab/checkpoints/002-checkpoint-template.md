# 检查点：统一学习记录模板

## 元数据

- `task_id`: `1.2`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `Windows 11 临时环境；正式环境快照将在任务 1.3 建立`
- `evidence`: `asr_lab/checkpoints/TEMPLATE.md`、`asr_lab/checkpoints/README.md`、`asr_lab/tests/test_checkpoints.py`

## 目标

建立所有后续任务共用的检查点格式，使每一步都能从目标追溯到实际命令、原始输出、解释和下一步门槛。

## 核心概念

- **过程证据**：不仅保留最后的通过或失败，还保留如何得到结论。
- **固定结构**：相同章节让不同 ASR 候选的学习记录容易查阅和比较。
- **可验证门槛**：只有下一步条件都有证据时，任务才能勾选完成。

## 入口命令

工作目录：`D:\workspace\ai\Voice\asr_lab\src`

```powershell
python -m unittest discover -s '..\tests' -v
```

## 预期结果

模板按固定顺序包含九个必填章节，首份检查点不存在空章节或未填写的命令与输出占位符。

## 实际输出

```text
test_scaffold_checkpoint_is_filled_and_reproducible ... ok
test_template_contains_every_required_section ... ok
Ran 4 tests in 0.001s
OK
```

## 结果解释

检查点格式不再只是文档约定，测试会在章节缺失、顺序变化、内容为空或首份记录仍有关键占位符时失败。它没有验证文字结论是否正确，结论仍必须由对应实验输出支持。

## 遇到的问题

无。

## 进入下一步的条件

- [x] 九个必填章节已经固定。
- [x] 检查点状态和命名规则已有说明。
- [x] 任务 1.1 已使用该格式形成真实记录。
- [x] 模板契约测试全部通过。

