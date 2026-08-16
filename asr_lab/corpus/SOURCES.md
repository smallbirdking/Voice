# v1 语料来源与许可

## 使用边界

v1 是本地学习和非商业评测语料。中文录音与由其构成的中英混合录音受
`CC BY-NC 4.0` 限制，因此整套 v1 不得直接用于商业基准或商业产品分发。
正式商用前必须替换这些样本并生成新的语料版本和指纹。

Tatoeba 的句子导出页面说明句子数据使用 `CC BY 2.0 FR`，而每个音频的许可证由
录音贡献者选择并记录在 `sentences_with_audio` 导出中。机器可读的筛选与摘要证据见
[`sources/tatoeba-v1-selection.json`](sources/tatoeba-v1-selection.json)。

## 第三方录音

| 样本 | 句子 / 音频 | 录音作者 | 录音许可 | 文本许可 | 本地处理 |
|---|---|---|---|---|---|
| `zh-short-command-001` | Tatoeba sentence 13817883 / audio 1284512 | zhoucantd | CC BY-NC 4.0 | CC BY 2.0 FR | MP3 无损解码为 PCM16 WAV |
| `zh-long-form-001` | Tatoeba sentence 13843227 / audio 1284524 | zhoucantd | CC BY-NC 4.0 | CC BY 2.0 FR | MP3 无损解码为 PCM16 WAV |
| `en-general-speech-001` | Tatoeba sentence 1646 / audio 1112877 | Them | CC BY 4.0 | CC BY 2.0 FR | MP3 无损解码为 PCM16 WAV |
| `en-short-command-001` | Tatoeba sentence 64007 / audio 1247321 | rul | CC BY 4.0 | CC BY 2.0 FR | MP3 无损解码为 PCM16 WAV |

上游 MP3 保存在 `corpus/source/upstream/`，避免只留下重新封装后的文件。四个输入 WAV
由固定的 FFmpeg 7.1 解码，移除容器元数据但不改变上游采样率和声道。

## 项目生成资产

- `zh-en-mixed-001`：依次拼接 `zh-short-command-001`、250 ms 静音、
  `en-short-command-001`。它是署名改编作品，继承两个片段中更严格的
  `CC BY-NC 4.0` 非商业限制。
- `silence-001`：`voice_asr_lab.corpus.assets` 生成的 2 秒 PCM16 静音，项目以
  `CC0-1.0` 提供。
- `noise-001`：使用固定种子 `0x564F4943` 的 xorshift32 生成 3 秒有界 PCM16 噪声，
  项目以 `CC0-1.0` 提供。它不是现实环境噪声，只用于验证静音误识别与鲁棒性管线。

## 许可证链接

- CC BY-NC 4.0: https://creativecommons.org/licenses/by-nc/4.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- CC BY 2.0 FR: https://creativecommons.org/licenses/by/2.0/fr/
- CC0 1.0: https://creativecommons.org/publicdomain/zero/1.0/
- Tatoeba downloads: https://tatoeba.org/en/downloads
