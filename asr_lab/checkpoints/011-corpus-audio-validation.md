# 检查点：语料音频一致性校验

## 元数据

- `task_id`: `2.3`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/src/voice_asr_lab/corpus/audio_validation.py`、`asr_lab/tests/test_audio_validation.py`

## 目标

把“清单 JSON 格式正确”推进为“清单描述与磁盘上的真实 WAV 内容一致”，并让每个失败样本给出可定位的原因。

## 核心概念

- JSON Schema 只能约束字段形状，不能证明文件存在，也不能读取 WAV 头或重新计算文件摘要。
- 音频摘要采用流式 SHA-256，避免把长音频一次性读入内存。
- 时长从 `frame_count / sample_rate` 推导，而不是相信清单中的声明值。
- 单个样本失败不会中断整批检查；报告保留每个样本的错误列表，便于一次修完所有问题。

## 入口命令

工作目录：`D:\workspace\ai\Voice`。

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m voice_asr_lab check-corpus-audio asr_lab/corpus/manifests/voice-asr-eval-v1.json
python -m unittest discover -s asr_lab/tests -p 'test_audio_validation.py' -v
```

## 预期结果

命令逐样本比较文件存在性、SHA-256、容器、编码、采样率、声道、位宽和时长；任一字段不一致时退出失败，并在对应样本下给出明确原因。

## 实际输出

```text
check-corpus-audio:
  status=passed
  sample_count=7
  passed=7
  failed=0

Ran 5 tests
OK
```

## 结果解释

真实 v1 语料的 7 个 WAV 全部与清单一致。测试另外人为制造了缺失文件、摘要错误、采样率/声道/时长不匹配和损坏 WAV，证明失败信息不是只覆盖成功路径。

## 遇到的问题

WAV 解析异常必须转成样本级错误；若让 `wave.Error` 直接终止进程，批量检查会丢失其他样本的诊断结果。实现因此捕获媒体解析错误并继续遍历。

## 进入下一步的条件

- [x] 七个真实样本全部通过内容检查。
- [x] 缺失文件和损坏 WAV 有明确错误。
- [x] 摘要、采样率、声道和时长不一致均有测试。
- [x] CLI 输出可被机器读取，并以退出码区分通过与失败。
- [x] 原始音频只读，没有被校验过程修改。
