# 检查点：中文参考文本规范化

## 元数据

- `task_id`: `2.5`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/corpus/text_normalization.py`、`asr_lab/tests/test_chinese_normalization.py`

## 目标

固定中文参考文本的第一版评分前处理，避免不同 Provider 的标点和空白风格被误计为识别错误。

## 核心概念

- 规则版本是 `text-normalization-v1`；规则变化必须在后续语料指纹中可见。
- 先执行 Unicode NFKC，将全角拉丁字母和数字转换为兼容的半角形式。
- 拉丁字母转小写；保留所有 Unicode 字母和数字；删除标点、符号与空白。
- 数字保持数字，不把 `2026` 猜测性转换成“二零二六”或“两千零二十六”。

## 入口命令

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m unittest discover -s asr_lab/tests -p 'test_chinese_normalization.py' -v
```

## 预期结果

标点和空白被删除，大小写和全半角统一，数字稳定保留，规则版本有测试锁定。

## 实际输出

```text
Ran 5 tests in 0.000s
OK
```

## 结果解释

例如 `ＡＳＲ１２３，测试。` 规范化为 `asr123测试`，`今天是2026年8月16日` 中的数字不会被改写。这样既减少无关差异，也避免语言学猜测污染参考答案。

## 遇到的问题

“删除标点”不能写成只删除中英文句号和逗号的枚举，否则新符号会漏过。实现根据 Unicode 字符类别仅保留字母与数字，规则更明确且可测试。

## 进入下一步的条件

- [x] 标点与空白规则有测试。
- [x] 拉丁大小写规则有测试。
- [x] 数字保留策略有测试。
- [x] 全角到半角的 NFKC 行为有测试。
- [x] 规范化版本被显式锁定。
