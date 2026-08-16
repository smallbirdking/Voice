# 检查点：英文参考文本规范化

## 元数据

- `task_id`: `2.6`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/corpus/text_normalization.py`、`asr_lab/tests/test_english_normalization.py`

## 目标

固定英文参考文本的第一版词元化与规范化规则，使大小写、排版空白和常见标点差异不影响 Provider 比较。

## 核心概念

- NFKC 先统一全角兼容字符，弯撇号再统一为 ASCII 撇号。
- 字母全部小写，连续词元用一个空格连接。
- 单词内部撇号保留，因此 `don't` 和 `isn't` 不会被拆成两个词元。
- `U.S.A.` 和 `Ph.D.` 的字母间句点删除，成为 `usa` 和 `phd`；连字符作为词边界。
- 小数点当前作为普通标点，所以 `2.0` 形成 `2 0`。这是显式的 v1 行为，不是隐藏假设。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m unittest discover -s asr_lab/tests -p 'test_english_normalization.py' -v
```

## 预期结果

大小写、空白、标点、缩写、撇号、连字符和兼容字符都有稳定且可测试的输出。

## 实际输出

```text
Ran 5 tests in 0.000s
OK
```

## 结果解释

英文参考被转换成面向 WER 的空格分隔词元串。规则不依赖第三方分词器，因此各 Provider 的同一结果可以在完全离线环境下复现。

## 遇到的问题

若简单删除全部撇号，缩写和所有格会改变词形；若把全部标点都替换为空格，`U.S.` 又会错误变成 `u s`。实现先处理字母缩写句点，再用只允许内部撇号的词元模式提取单词。

## 进入下一步的条件

- [x] 大小写、标点和空白规则有测试。
- [x] 内部直撇号和弯撇号有测试。
- [x] 点号缩写有测试。
- [x] 连字符和数字标点行为有测试。
- [x] 全角兼容字符有测试。
