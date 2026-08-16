# 本地 ASR 网络边界

本实验允许在模型准备阶段访问外部网络，以下载依赖、模型文件和许可元数据。允许下载模型不等于允许上传实验数据：测试音频、参考文本、转写结果和资源采样在任何阶段都不得发送到外部服务。

推理与报告阶段默认阻断外网。`127.0.0.0/8`、`::1` 和 `localhost` loopback 保留给同一基准机器上的本地服务，例如以后可能运行的 NIM 容器；loopback 不代表云端 API。

机器可读规则位于 `network-policy.json`。如果一个候选只有把测试音频发送到外部云服务才能工作，应保存退出原因，不运行该路径，也不能用云端结果代表本地候选。

## 当前可执行验证

在 `asr_lab/src` 执行：

```powershell
python -m voice_asr_lab prepare-synthetic-cache
python -m voice_asr_lab offline-smoke
```

第一条命令只生成一个 40 字节的本地缓存标记，用来模拟“模型已经准备好”。第二条命令先根据保留的清单校验路径、大小和 SHA-256，再进入 Python socket 外网守卫。烟雾测试会尝试连接保留域名 `example.invalid`，并要求该操作在 DNS 查询之前被守卫拒绝；随后只在内存中处理合成静音 PCM 和缓存标记。

这个烟雾测试证明当前 Python 进程不依赖外网，不证明未来第三方原生库或子进程无法绕过 Python socket。每个真实 Provider 接入时仍需根据它的进程边界补充操作系统、容器或网络命名空间级隔离证据。当前输出会明确记录这一 enforcement scope，避免把应用层守卫夸大为整机防火墙。
