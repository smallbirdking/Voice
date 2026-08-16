# 检查点：实验资产目录与 Git 边界

## 元数据

- `task_id`: `1.5`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `Git repository；storage-layout schema 1.0.0`
- `evidence`: `asr_lab/storage-layout.json`、`asr_lab/.gitignore`、`asr_lab/STORAGE.md`、`asr_lab/tests/test_storage_layout.py`

## 目标

在下载任何模型或生成实验结果之前，先固定模型缓存、语料、临时结果、保留报告和日志的目录边界。通过自动化测试证明日常 Git 操作不会误收大模型和可再生成的临时产物，同时确保重现实验所需的小型清单、原始语料和报告仍可进入版本控制。

## 核心概念

实验资产不能只按文件格式决定是否提交，而应按“是否是重现实验所需证据”分类：

- `models/cache/` 保存可重新下载的模型载荷，忽略；`models/manifests/` 保存模型身份、来源和摘要，保留。
- `corpus/source/` 和 `corpus/manifests/` 是固定语料输入，保留；`corpus/derived/` 可以确定性重建，忽略。
- `tmp/` 是尚未审核的中间结果，忽略；`reports/` 是审核后用于比较和复盘的证据，保留。
- `logs/` 是可重复产生的详细诊断信息，忽略。

Git 不记录空目录，所以每个新目录放置 `.gitkeep` 标记。对于应忽略的目录，`.gitignore` 使用“先忽略全部内容、再放行 `.gitkeep`”的规则，既保存结构又不放行真实载荷。

`git check-ignore --no-index` 可以检查尚不存在、尚未被跟踪的代表路径。因此测试不需要创建几个 GiB 的真实模型，也能验证未来模型文件会命中正确规则。

## 入口命令

在 `asr_lab/src` 目录运行专项测试：

```powershell
python -m unittest discover -s '..\tests' -p 'test_storage_layout.py' -v
```

运行完整测试：

```powershell
python -m unittest discover -s '..\tests' -v
```

在仓库根目录查看代表路径命中的规则：

```powershell
git check-ignore -v --no-index -- `
  asr_lab/models/cache/funasr/model.safetensors `
  asr_lab/corpus/derived/v1/sample-16khz.wav `
  asr_lab/tmp/run-in-progress/raw-results.jsonl `
  asr_lab/logs/funasr/debug.log
```

## 预期结果

- `storage-layout.json` 声明全部八类目录、Git 策略、保留策略和用途，且目录实际存在。
- 模型载荷、派生音频、临时结果和日志被 Git 忽略。
- 模型清单、原始语料、语料清单和保留报告不被忽略。
- 被忽略目录中的 `.gitkeep` 仍可追踪。
- 所有既有环境探测和检查点测试继续通过。

## 实际输出

专项测试结果：

```text
Ran 4 tests in 0.323s
OK
```

Git 对四类本地产物给出的匹配证据：

```text
asr_lab/.gitignore:7:/models/cache/*  asr_lab/models/cache/funasr/model.safetensors
asr_lab/.gitignore:11:/corpus/derived/*  asr_lab/corpus/derived/v1/sample-16khz.wav
asr_lab/.gitignore:15:/tmp/*  asr_lab/tmp/run-in-progress/raw-results.jsonl
asr_lab/.gitignore:17:/logs/*  asr_lab/logs/funasr/debug.log
```

加入目录测试后的完整结果：

```text
Ran 19 tests in 0.515s
OK
```

## 结果解释

当前目录策略既防止大模型和临时数据被普通 `git add` 误收，也没有粗暴地忽略整个 `models/` 或 `corpus/`。后者很重要：如果模型清单和语料清单也被忽略，仓库中虽然没有大文件，却同样无法重现实验。

`reports/` 与 `tmp/` 的分离形成了一个显式晋升过程：运行中的原始草稿先进入 `tmp/`，经过完整性检查、补齐环境与输入标识后，值得长期保留的结果才写入 `reports/`。任务 1.6 将为这个关联过程定义运行标识和环境快照标识。

## 遇到的问题

空目录本身不会被 Git 保存，因此增加了 `.gitkeep`，并为四个默认忽略目录添加放行例外。文档中的专项测试命令最初没有按照当前 `asr_lab/src` 工作目录编写，在执行前已改为 `unittest discover` 的可复现形式。

`.gitignore` 防止的是日常误提交，无法阻止开发者显式使用 `git add -f` 强制加入文件；这是 Git 的既定行为。自动化测试会在忽略规则被意外删除或放宽时失败，但仍需要代码评审避免故意绕过规则。

## 进入下一步的条件

- 模型缓存、版本化语料、派生语料、临时结果、保留报告和日志目录均已定义并存在。
- 每类目录的 Git 与保留策略均有机器可读记录和中文解释。
- 大模型与临时产物的忽略规则、复现证据的可追踪性和目录标记均通过自动化测试。
- 完整测试为 19/19 通过，可以开始任务 1.6：定义实验运行标识和环境快照标识。
