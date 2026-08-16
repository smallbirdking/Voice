# 检查点：模型下载与本地音频网络边界

## 元数据

- `task_id`: `1.7`
- `status`: `complete`
- `recorded_at`: `2026-08-16`
- `environment`: `local-asr-no-cloud-audio policy 1.0.0；Python socket guard`
- `evidence`: `asr_lab/network-policy.json`、`asr_lab/NETWORK_POLICY.md`、`asr_lab/src/voice_asr_lab/system/offline_boundary.py`、`asr_lab/tests/test_offline_boundary.py`

## 目标

把“允许下载依赖和模型，但禁止向云端发送测试音频”从口头约束变成机器可读策略和可执行验证。证明缓存内容完整后，合成烟雾测试可以在阻断外部网络的情况下完成，同时保留同一基准机器上的 loopback 服务能力。

## 核心概念

网络权限必须同时考虑“阶段”和“数据类别”。模型准备阶段允许下载依赖、模型、模型元数据和许可信息，但测试音频、参考文本、转写输出和资源采样仍然禁止外发。推理和报告阶段阻断外部网络。

`127.0.0.0/8`、`::1` 和 `localhost` 是本机 loopback，不会把数据送出基准机器，因此保留给未来可能运行在本机容器中的 NIM 服务。其他主机名和 IP 在 Python 守卫中会在 DNS 查询或连接之前被拒绝。

缓存就绪不能只看文件是否存在。烟雾测试先根据保留清单核对相对路径没有逃逸缓存根目录，再核对文件大小和 SHA-256。缓存缺失或被篡改时，测试在进入执行阶段之前失败。

本步骤的“合成烟雾测试”只读取缓存标记并计算 100ms 合成静音 PCM 的本地摘要，明确输出 `asr_inference_performed: false`。它验证的是缓存和网络边界，不是任务 3.4 的合成 Provider，也不是任何真实 ASR 的准确率证据。

## 入口命令

在 `asr_lab/src` 目录准备确定性本地缓存：

```powershell
python -m voice_asr_lab prepare-synthetic-cache
```

缓存准备好后执行外网阻断烟雾测试：

```powershell
python -m voice_asr_lab offline-smoke
```

运行专项和完整测试：

```powershell
python -m unittest discover -s '..\tests' -p 'test_offline_boundary.py' -v
python -m unittest discover -s '..\tests' -v
```

## 预期结果

- 网络策略明确允许模型准备阶段下载模型，但任何阶段都禁止外发测试音频。
- 合成缓存标记与保留清单的路径、40 字节大小和 SHA-256 完全匹配。
- 缓存缺失或篡改时，离线烟雾测试返回 `cache-not-ready`。
- 对 `example.invalid:443` 的连接在 DNS 之前被阻断。
- loopback TCP 连接仍然可用。
- 合成音频完全在本地处理，外发字节数为 0。
- 模型缓存产物继续被 Git 忽略。

## 实际输出

真实缓存准备结果：

```json
{
  "status": "ready",
  "model_id": "synthetic-smoke-cache-v1",
  "size_bytes": 40,
  "sha256": "28a5727456f439abd1f7660df0e98ab125e4884165cca089c256e8eefc845e8a",
  "network_used": false
}
```

真实外网阻断烟雾测试的关键结果：

```json
{
  "status": "passed",
  "cache_ready": true,
  "asr_inference_performed": false,
  "operation": "local-cache-read-and-synthetic-pcm-hash",
  "network": {
    "external_network": "blocked",
    "loopback_network": "allowed",
    "block_verified_before_dns": true,
    "verification_destination": "example.invalid:443",
    "test_audio_bytes_sent_external": 0,
    "enforcement_scope": "current-python-process-socket-api"
  },
  "local_result_digest": "43a81ca64acff1f42d944919e6d4a1fe3696a74f389c5b291ae0d13571861da7",
  "errors": []
}
```

Git 确认缓存标记命中 `asr_lab/.gitignore` 的 `/models/cache/*` 规则。专项测试为 `Ran 7 tests ... OK`，完整回归为 `Ran 33 tests ... OK`。

## 结果解释

实验执行现在可以明确区分两个动作：联网准备公开模型资产，以及在本机使用已经验证的缓存处理音频。后者不会因为模型下载器的隐式联网行为而静默退化成云端调用。

烟雾测试故意使用保留域名 `example.invalid` 验证阻断，而且测试确认 DNS 解析函数没有被调用。这比等待一个真实网址连接超时更确定，也不会向真实服务发送请求。

允许 loopback 是为本地服务型 Runtime 保留必要通道。以后测试 NIM 时仍要证明服务运行在同一基准机器，并证明容器本身没有把音频继续转发到外部。

## 遇到的问题

在当前受管终端中，第一次向默认 `models/cache/synthetic-smoke/` 创建文件时被沙箱拒绝；目录 ACL 本身允许修改，因此使用一次精确授权生成了 40 字节缓存标记。缓存生成后，普通受限环境能够读取它并完成离线测试。这属于执行环境写入限制，不是烟雾测试对网络或模型下载的依赖。

Python socket 守卫会影响当前进程中的 `socket.create_connection`、DNS 解析、`connect` 和 `connect_ex`，但无法证明第三方原生库、单独子进程或容器不能绕过它。因此输出明确记录 enforcement scope。每个真实 Provider 后续仍需按其进程边界补充操作系统或容器级阻断证据，不能直接沿用本步骤的结论。

## 进入下一步的条件

- 模型准备、推理和报告三阶段的网络及数据边界已有机器可读记录。
- 缓存完整性、篡改拒绝、外部连接阻断和 loopback 放行均有自动化测试。
- 默认缓存就绪后，真实命令在外部网络阻断状态下完成本地合成烟雾测试。
- 输出明确表明测试音频外发 0 字节，并且没有声称完成真实 ASR 推理。
- 完整测试为 33/33 通过，可以开始任务 1.8：保存第一份机器可读环境基线快照和学习说明。
