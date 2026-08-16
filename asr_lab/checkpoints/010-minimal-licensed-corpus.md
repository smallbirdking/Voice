# 检查点：最小许可语料

## 元数据

- `task_id`: `2.2`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- `evidence`: `asr_lab/corpus/manifests/voice-asr-eval-v1.json`、`asr_lab/corpus/SOURCES.md`、`asr_lab/corpus/sources/tatoeba-v1-selection.json`、`asr_lab/corpus/source/`

## 目标

准备一套足够小、可以进入所有 Provider 烟雾与准确率管线、同时来源和再分发条件逐条可审计的 v1 音频集合。

## 核心概念

- 句子文本许可和录音许可是两个独立事实。Tatoeba 文本使用 `CC BY 2.0 FR`，录音使用贡献者逐条选择的许可证。
- 中文录音是 `CC BY-NC 4.0`，允许改编但限制商业使用；这使 v1 适合当前学习评测，却不能未经替换进入商业基准。
- 上游 MP3 与解码后的 PCM WAV 同时保留。前者证明取得的原件，后者让后续媒体检查和确定性预处理只依赖 Python 标准库。
- 中英混合样本是两段已许可语音的组合改编，继承更严格的非商业限制；静音和伪随机噪声由项目确定性生成并采用 CC0。

## 入口命令

工作目录：`D:\workspace\ai\Voice`。

```powershell
$env:PYTHONPATH = 'asr_lab/src'
python -m voice_asr_lab prepare-corpus-owned-assets --source-root asr_lab/corpus/source
python -m voice_asr_lab validate-corpus-manifest asr_lab/corpus/manifests/voice-asr-eval-v1.json
python -m unittest discover -s asr_lab/tests -p 'test_corpus_manifest.py' -v
```

第一条命令采用拒绝覆盖语义；它记录首次生成方式，已有资产上重复执行会明确失败，避免静默改写 v1 输入。

## 预期结果

清单包含中文、英文、中英混合、静音和纯噪声语言模式，并由长句、普通语音和短命令场景共同覆盖规格要求。每条样本必须有非空许可标识和证据路径，受非商业限制的记录必须显式标为 `restricted`。

## 实际输出

```text
prepare-corpus-owned-assets:
  silence-001.wav  duration_ms=2000  channels=2
  noise-001.wav    duration_ms=3000  channels=2
  zh-en-mixed-001.wav duration_ms=3907 channels=1

validate-corpus-manifest:
  status=valid
  corpus_id=voice-asr-eval
  corpus_version=v1
  sample_count=7
  errors=[]

Ran 11 tests in 0.008s
OK
```

源目录另外保留四个 Tatoeba MP3 原件。录音作者分别为 `zhoucantd`、`Them` 和 `rul`；选择证据同时保存 sentence ID、audio ID、下载地址、许可证、原件摘要、WAV 摘要和固定 FFmpeg 版本。

## 结果解释

结果证明 v1 已具备规格要求的最小类别覆盖和逐样本来源证据。它尚未证明磁盘上的 WAV 与清单摘要、采样率、声道和时长全部一致；当前 CLI 只校验清单结构，这个差异正是下一步 2.3 要解决的问题。

## 遇到的问题

本机 Windows SAPI 语音可以离线合成，但官方条款没有明确授予桌面语音输出的再分发权，因此没有把它伪装成自有语料。Tatoeba 可改编的中文录音只有 `CC BY-NC 4.0`，所以保留它的非商业限制，并把未来商用替换要求写入来源说明。

## 进入下一步的条件

- [x] 七类最低覆盖均可映射到至少一个清单样本。
- [x] 每条样本都登记来源、作者或生成算法、许可和证据。
- [x] 上游第三方文件与本地改编摘要均已保留。
- [x] 清单结构与许可覆盖测试通过。
- [x] 未把结构校验误写成音频内容校验。
