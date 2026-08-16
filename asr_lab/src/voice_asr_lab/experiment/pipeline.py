"""End-to-end synthetic experiment composed from the common lab tools."""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from voice_asr_lab import __version__
from voice_asr_lab.core.identifiers import create_run_id, validate_run_context
from voice_asr_lab.corpus.manifest import load_corpus_manifest, validate_corpus_manifest
from voice_asr_lab.corpus.text_normalization import normalize_reference
from voice_asr_lab.experiment.events import validate_stream_events
from voice_asr_lab.experiment.replay import AudioChunk, load_wave_audio, replay_wave
from voice_asr_lab.experiment.report import build_experiment_report, write_experiment_report
from voice_asr_lab.experiment.resources import ResourceSampler, validate_resource_sample
from voice_asr_lab.experiment.sample_result import validate_sample_result
from voice_asr_lab.experiment.synthetic_provider import (
    SyntheticProvider,
    SyntheticProviderConfig,
    SyntheticRunContext,
)
from voice_asr_lab.experiment.timing import Clock, SystemClock, format_utc
from voice_asr_lab.system.baseline import validate_environment_baseline


@dataclass(frozen=True)
class SyntheticExperimentArtifacts:
    output_dir: Path
    run_context_path: Path
    sample_results_path: Path
    resource_samples_path: Path
    event_paths: tuple[Path, ...]
    report_json_path: Path
    report_markdown_path: Path
    learning_path: Path
    report: dict[str, Any]


def run_synthetic_experiment(
    manifest_path: Path,
    derived_root: Path,
    environment_baseline_path: Path,
    output_dir: Path,
    *,
    clock: Clock | None = None,
    resource_sampler: ResourceSampler | None = None,
    run_id: str | None = None,
) -> SyntheticExperimentArtifacts:
    """Run the entire v1 corpus through the deterministic synthetic provider once."""

    if output_dir.exists():
        raise FileExistsError(f"synthetic experiment output already exists: {output_dir.resolve()}")
    manifest = load_corpus_manifest(manifest_path)
    manifest_errors = validate_corpus_manifest(manifest)
    if manifest_errors:
        raise ValueError("invalid corpus manifest: " + "; ".join(manifest_errors))
    baseline = _load_object(environment_baseline_path, "environment baseline")
    baseline_errors = validate_environment_baseline(baseline)
    if baseline_errors:
        raise ValueError("invalid environment baseline: " + "; ".join(baseline_errors))

    active_clock = clock or SystemClock()
    active_run_id = run_id or create_run_id()
    run_context = {
        "schema_version": "1.0.0",
        "run_id": active_run_id,
        "environment_snapshot_id": baseline["environment_snapshot_id"],
        "created_at": format_utc(active_clock.utc_now()),
    }
    context_errors = validate_run_context(run_context)
    if context_errors:
        raise ValueError("invalid run context: " + "; ".join(context_errors))

    sampler = resource_sampler or ResourceSampler(active_clock)
    sample_results: list[dict[str, Any]] = []
    resource_samples: list[dict[str, Any]] = []
    events_by_sample: dict[str, tuple[dict[str, Any], ...]] = {}
    replay_summaries: dict[str, dict[str, Any]] = {}

    for sample in manifest["samples"]:
        sample_id = sample["sample_id"]
        audio = load_wave_audio(derived_root / f"{sample_id}.wav")
        chunks: list[AudioChunk] = []
        replay = replay_wave(
            audio, chunk_ms=200, mode="offline", clock=active_clock, sink=chunks.append
        )
        replay_summaries[sample_id] = asdict(replay)
        if b"".join(chunk.pcm_bytes for chunk in chunks) != audio.pcm_bytes:
            raise ValueError(f"offline replay changed PCM bytes: {sample_id}")

        session_id = f"session-{sample_id}"
        resource_context = {
            "run_id": active_run_id,
            "environment_snapshot_id": run_context["environment_snapshot_id"],
            "provider_id": "synthetic",
            "session_id": session_id,
            "sample_id": sample_id,
        }
        started_ns = active_clock.monotonic_ns()
        started_at = format_utc(active_clock.utc_now())
        before = sampler.sample(resource_context)
        config = _config_for_sample(sample)
        provider_run = SyntheticProvider(config, active_clock).run(
            SyntheticRunContext(
                run_id=active_run_id,
                environment_snapshot_id=run_context["environment_snapshot_id"],
                sample_id=sample_id,
                session_id=session_id,
            ),
            audio=audio.pcm_bytes,
            audio_duration_ms=audio.duration_ms,
        )
        after = sampler.sample(resource_context)
        finished_ns = active_clock.monotonic_ns()
        finished_at = format_utc(active_clock.utc_now())

        event_errors = validate_stream_events(provider_run.events)
        if event_errors:
            raise ValueError(f"synthetic events are invalid for {sample_id}: {'; '.join(event_errors)}")
        for resource in (before, after):
            resource_errors = validate_resource_sample(resource)
            if resource_errors:
                raise ValueError(
                    f"resource sample is invalid for {sample_id}: {'; '.join(resource_errors)}"
                )
        result = _build_sample_result(
            manifest, sample, audio, config, provider_run, before, after,
            started_ns, started_at, finished_ns, finished_at,
        )
        result_errors = validate_sample_result(result)
        if result_errors:
            raise ValueError(f"sample result is invalid for {sample_id}: {'; '.join(result_errors)}")
        sample_results.append(result)
        resource_samples.extend((before, after))
        events_by_sample[sample_id] = provider_run.events

    report = build_experiment_report(sample_results, manifest, generated_at=format_utc(active_clock.utc_now()))
    return _write_artifacts(
        output_dir, run_context, sample_results, resource_samples,
        events_by_sample, replay_summaries, report, manifest_path, derived_root,
        environment_baseline_path,
    )


def _build_sample_result(
    manifest: dict[str, Any],
    sample: dict[str, Any],
    audio: Any,
    config: SyntheticProviderConfig,
    provider_run: Any,
    before: dict[str, Any],
    after: dict[str, Any],
    started_ns: int,
    started_at: str,
    finished_ns: int,
    finished_at: str,
) -> dict[str, Any]:
    events = provider_run.events
    inference_start = next(event for event in events if event["event_type"] == "consumption_started")
    inference_finish = next(
        event for event in reversed(events) if event["event_type"] in {"final", "cancelled"}
    )
    reference_version = sample["reference"]["normalization_version"]
    raw_text = provider_run.raw_text
    if provider_run.status == "succeeded":
        normalized_text = (
            normalize_reference(raw_text, sample["language"])["normalized_text"]
            if sample["language"] != "none" else ""
        )
        normalization_version = reference_version
    else:
        normalized_text = None
        normalization_version = reference_version
    return {
        "schema_version": "1.0.0",
        "record_type": "sample_result",
        "run_id": events[0]["run_id"],
        "environment_snapshot_id": events[0]["environment_snapshot_id"],
        "corpus": {
            "corpus_id": manifest["corpus_id"],
            "corpus_version": manifest["corpus_version"],
            "corpus_fingerprint": manifest["corpus_fingerprint"],
            "reference_normalization_version": reference_version,
        },
        "input": {
            "sample_id": sample["sample_id"], "language": sample["language"],
            "scenario": sample["scenario"],
            "audio": {
                "path": f"derived/{manifest['corpus_version']}/{sample['sample_id']}.wav",
                "sha256": hashlib.sha256(audio.path.read_bytes()).hexdigest(),
                "duration_ms": round(audio.duration_ms),
                "format": {
                    "container": "wav", "codec": "pcm-s16le",
                    "sample_rate_hz": audio.sample_rate_hz, "channels": audio.channels,
                    "sample_width_bits": audio.sample_width_bits,
                },
            },
        },
        "provider": {
            "provider_id": "synthetic", "implementation_version": __version__,
            "runtime": {
                "name": platform.python_implementation(),
                "version": platform.python_version(), "device": "cpu",
            },
        },
        "model": {
            "model_id": "synthetic-deterministic-v1", "revision": "v1",
            "artifact_fingerprint": None,
        },
        "configuration": asdict(config),
        "transcription": {
            "raw_text": raw_text, "normalized_text": normalized_text,
            "normalization_version": normalization_version,
            "detected_language": sample["language"] if sample["language"] != "none" else None,
            "provider_payload": {
                "status": provider_run.status, "event_count": len(events),
                "event_ids": [event["event_id"] for event in events],
            },
        },
        "timing": {
            "started_at": started_at, "finished_at": finished_at,
            "monotonic_started_ns": started_ns,
            "inference_started_ns": inference_start["monotonic_ns"],
            "inference_finished_ns": inference_finish["monotonic_ns"],
            "monotonic_finished_ns": finished_ns,
            "inference_duration_ms": (
                inference_finish["monotonic_ns"] - inference_start["monotonic_ns"]
            ) / 1_000_000,
            "total_duration_ms": (finished_ns - started_ns) / 1_000_000,
        },
        "outcome": {
            "status": provider_run.status, "process_exit_code": 0 if provider_run.status == "succeeded" else 1,
            "error": provider_run.error,
        },
        "resource_sample_refs": [before["resource_sample_id"], after["resource_sample_id"]],
    }


def _config_for_sample(sample: dict[str, Any]) -> SyntheticProviderConfig:
    raw_text = sample["reference"]["text"] or ""
    normalized = sample["reference"]["normalized_text"] or ""
    if normalized:
        partials = tuple(dict.fromkeys((normalized[: max(1, len(normalized) // 2)], normalized)))
    else:
        partials = ()
    return SyntheticProviderConfig(
        partial_texts=partials, final_text=raw_text, queue_delay_ms=1,
        partial_interval_ms=4, endpoint_delay_ms=2, final_delay_ms=3,
    )


def _write_artifacts(
    output_dir: Path,
    run_context: dict[str, Any],
    sample_results: list[dict[str, Any]],
    resource_samples: list[dict[str, Any]],
    events_by_sample: dict[str, tuple[dict[str, Any], ...]],
    replay_summaries: dict[str, dict[str, Any]],
    report: dict[str, Any],
    manifest_path: Path,
    derived_root: Path,
    environment_baseline_path: Path,
) -> SyntheticExperimentArtifacts:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    events_dir = output_dir / "events"
    events_dir.mkdir()
    run_context_path = output_dir / "run-context.json"
    sample_results_path = output_dir / "sample-results.jsonl"
    resource_samples_path = output_dir / "resource-samples.jsonl"
    replay_path = output_dir / "replay-summaries.json"
    report_json_path = output_dir / "report.json"
    report_markdown_path = output_dir / "report.md"
    learning_path = output_dir / "README.md"
    _write_json(run_context_path, run_context)
    _write_jsonl(sample_results_path, sample_results)
    _write_jsonl(resource_samples_path, resource_samples)
    _write_json(replay_path, replay_summaries)
    event_paths: list[Path] = []
    for sample_id, events in events_by_sample.items():
        event_path = events_dir / f"{sample_id}.jsonl"
        _write_jsonl(event_path, events)
        event_paths.append(event_path)
    write_experiment_report(report, report_json_path, report_markdown_path)
    learning_path.write_text(
        _render_learning_index(
            report, manifest_path, derived_root, environment_baseline_path, events_by_sample
        ),
        encoding="utf-8", newline="\n",
    )
    return SyntheticExperimentArtifacts(
        output_dir, run_context_path, sample_results_path, resource_samples_path,
        tuple(event_paths), report_json_path, report_markdown_path, learning_path, report,
    )


def _render_learning_index(
    report: dict[str, Any],
    manifest_path: Path,
    derived_root: Path,
    baseline_path: Path,
    events_by_sample: dict[str, tuple[dict[str, Any], ...]],
) -> str:
    return f"""# 合成 Provider 端到端实验

## 入口命令

```powershell
$env:PYTHONPATH = \"asr_lab/src\"
python -m voice_asr_lab run-synthetic-experiment {manifest_path.as_posix()} `
  --derived-root {derived_root.as_posix()} `
  --environment-baseline {baseline_path.as_posix()} `
  --output-dir <new-output-directory>
```

## 文件与字段

- `run-context.json`：一次运行及其精确环境快照关联。
- `events/<sample_id>.jsonl`：partial、endpoint、final、取消和关闭等不可变流式事实。
- `resource-samples.jsonl`：CPU、RSS、GPU 或采集错误；逐样本结果使用 ID 引用。
- `sample-results.jsonl`：输入、Provider、模型、配置、文字、时间和 outcome 原始事实。
- `replay-summaries.json`：离线回放的块数、字节数、音频时长与逻辑耗时。
- `report.json`：从事实与语料参考派生的准确率、RTF、完整性和失败清单。
- `report.md`：相同报告的人工学习视图。

本次运行 `{report['run_id']}` 共处理 {report['summary']['sample_count']} 个样本，保存
{sum(len(events) for events in events_by_sample.values())} 条事件；成功 {report['summary']['succeeded_count']}，
失败 {report['summary']['failed_count']}。`synthetic` 只证明公共工具管线，不证明真实 ASR 能力。
"""


def _load_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _write_jsonl(path: Path, values: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
