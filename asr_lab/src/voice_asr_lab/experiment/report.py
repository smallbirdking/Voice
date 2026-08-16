"""Aggregate per-sample raw JSONL into machine and learning reports."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from voice_asr_lab.corpus.manifest import validate_corpus_manifest
from voice_asr_lab.experiment.metrics import compute_sample_metrics
from voice_asr_lab.experiment.sample_result import validate_sample_result
from voice_asr_lab.experiment.timing import format_utc


REPORT_SCHEMA_VERSION = "1.0.0"


def load_sample_results_jsonl(path: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise ValueError(f"line {line_number}: blank JSONL lines are not allowed")
            result = json.loads(line)
            if not isinstance(result, dict):
                raise ValueError(f"line {line_number}: sample result must be a JSON object")
            errors = validate_sample_result(result)
            if errors:
                raise ValueError(f"line {line_number}: invalid sample result: {'; '.join(errors)}")
            results.append(result)
    if not results:
        raise ValueError("sample result JSONL must contain at least one result")
    return results


def build_experiment_report(
    results: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a report while preserving every valid failed sample record."""

    manifest_errors = validate_corpus_manifest(manifest)
    if manifest_errors:
        raise ValueError(f"invalid corpus manifest: {'; '.join(manifest_errors)}")
    if not results:
        raise ValueError("cannot aggregate an empty result set")
    for index, result in enumerate(results):
        errors = validate_sample_result(result)
        if errors:
            raise ValueError(f"result {index} is invalid: {'; '.join(errors)}")

    manifest_samples = {sample["sample_id"]: sample for sample in manifest["samples"]}
    _validate_result_set(results, manifest, manifest_samples)
    samples: list[dict[str, Any]] = []
    outcomes: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []

    for result in results:
        input_record = result["input"]
        sample_id = input_record["sample_id"]
        manifest_sample = manifest_samples[sample_id]
        status = result["outcome"]["status"]
        outcomes[status] += 1
        metrics = None
        if status == "succeeded":
            reference = manifest_sample["reference"]["normalized_text"] or ""
            hypothesis = result["transcription"]["normalized_text"] or ""
            keywords = (reference,) if input_record["scenario"] == "short-command" else ()
            metrics = compute_sample_metrics(
                language=input_record["language"],
                scenario=input_record["scenario"],
                reference=reference,
                hypothesis=hypothesis,
                audio_duration_ms=input_record["audio"]["duration_ms"],
                inference_duration_ms=result["timing"]["inference_duration_ms"],
                keywords=keywords,
            )
        else:
            failures.append(
                {
                    "sample_id": sample_id,
                    "status": status,
                    "error": result["outcome"]["error"],
                }
            )
        samples.append(
            {
                "sample_id": sample_id,
                "language": input_record["language"],
                "scenario": input_record["scenario"],
                "status": status,
                "normalized_reference": manifest_sample["reference"]["normalized_text"],
                "normalized_hypothesis": result["transcription"]["normalized_text"],
                "metrics": metrics,
                "resource_sample_refs": result["resource_sample_refs"],
                "error": result["outcome"]["error"],
            }
        )

    failed_count = len(results) - outcomes["succeeded"]
    first = results[0]
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_type": "asr_experiment_aggregate",
        "status": "passed" if failed_count == 0 else "completed_with_failures",
        "generated_at": generated_at or format_utc(datetime.now(timezone.utc)),
        "run_id": first["run_id"],
        "environment_snapshot_id": first["environment_snapshot_id"],
        "provider": first["provider"],
        "model": first["model"],
        "corpus": {
            "corpus_id": manifest["corpus_id"],
            "corpus_version": manifest["corpus_version"],
            "corpus_fingerprint": manifest["corpus_fingerprint"],
        },
        "summary": {
            "sample_count": len(results),
            "succeeded_count": outcomes["succeeded"],
            "failed_count": failed_count,
            "outcome_counts": dict(sorted(outcomes.items())),
        },
        "accuracy": {
            "cer": _aggregate_edit_rate(samples, "cer"),
            "wer": _aggregate_edit_rate(samples, "wer"),
            "mixed_error": _aggregate_edit_rate(samples, "mixed_error"),
            "keyword": _aggregate_keyword(samples),
            "silence": _aggregate_silence(samples),
        },
        "performance": _aggregate_realtime_factor(samples),
        "samples": samples,
        "failures": failures,
    }


def render_experiment_report_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# ASR 实验聚合报告", "", "## 运行边界", "",
        f"- 状态：`{report['status']}`",
        f"- 运行：`{report['run_id']}`",
        f"- 环境：`{report['environment_snapshot_id']}`",
        f"- Provider：`{report['provider']['provider_id']}`",
        f"- 模型：`{report['model']['model_id']}`",
        f"- 语料：`{report['corpus']['corpus_id']}:{report['corpus']['corpus_version']}`",
        "", "## 完整性", "",
        f"- 总样本：{summary['sample_count']}",
        f"- 成功：{summary['succeeded_count']}",
        f"- 失败或未完成：{summary['failed_count']}",
        "", "## 指标", "",
        "| 指标 | 已评估样本 | 分子 | 分母 | 结果 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for key in ("cer", "wer", "mixed_error"):
        metric = report["accuracy"][key]
        lines.append(
            f"| {key} | {metric['evaluated_samples']} | {metric['edit_distance']} | "
            f"{metric['reference_units']} | {_display(metric['rate'])} |"
        )
    keyword = report["accuracy"]["keyword"]
    silence = report["accuracy"]["silence"]
    performance = report["performance"]
    lines.extend(
        [
            f"| keyword sample hit | {keyword['evaluated_samples']} | {keyword['hit_samples']} | "
            f"{keyword['evaluated_samples']} | {_display(keyword['sample_hit_rate'])} |",
            f"| silence false recognition | {silence['evaluated_samples']} | "
            f"{silence['false_recognition_samples']} | {silence['evaluated_samples']} | "
            f"{_display(silence['false_recognition_rate'])} |",
            "", "## 样本明细", "",
            "| sample_id | 语言 | 场景 | 状态 | RTF | 错误 |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for sample in report["samples"]:
        rtf = sample["metrics"]["realtime_factor"] if sample["metrics"] else None
        error = sample["error"]["code"] if sample["error"] else ""
        lines.append(
            f"| {_cell(sample['sample_id'])} | {_cell(sample['language'])} | "
            f"{_cell(sample['scenario'])} | {_cell(sample['status'])} | {_display(rtf)} | {_cell(error)} |"
        )
    lines.extend(
        [
            "", "## 性能摘要", "",
            f"成功样本 RTF：count={performance['evaluated_samples']}，"
            f"mean={_display(performance['mean_realtime_factor'])}，"
            f"max={_display(performance['max_realtime_factor'])}。",
            "", "失败样本保留在明细和 `failures` 中；准确率只对存在合法识别输出的成功样本计算，失败数量单独报告，未被静默删除。", "",
        ]
    )
    return "\n".join(lines)


def write_experiment_report(
    report: Mapping[str, Any], json_path: Path, markdown_path: Path
) -> tuple[Path, Path]:
    json_path = json_path.resolve()
    markdown_path = markdown_path.resolve()
    if json_path == markdown_path:
        raise ValueError("JSON and Markdown report paths must differ")
    existing = [str(path) for path in (json_path, markdown_path) if path.exists()]
    if existing:
        raise FileExistsError(f"report output already exists: {', '.join(existing)}")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    with markdown_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(render_experiment_report_markdown(report))
    return json_path, markdown_path


def _validate_result_set(
    results: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    manifest_samples: Mapping[str, Mapping[str, Any]],
) -> None:
    first = results[0]
    shared_fields = ("run_id", "environment_snapshot_id", "provider", "model")
    sample_ids: list[str] = []
    for result in results:
        for field in shared_fields:
            if result[field] != first[field]:
                raise ValueError(f"all results must share {field}")
        corpus = result["corpus"]
        for field in ("corpus_id", "corpus_version", "corpus_fingerprint"):
            if corpus[field] != manifest[field]:
                raise ValueError(f"result corpus {field} does not match manifest")
        sample_id = result["input"]["sample_id"]
        if sample_id not in manifest_samples:
            raise ValueError(f"result sample is absent from manifest: {sample_id}")
        manifest_sample = manifest_samples[sample_id]
        for field in ("language", "scenario"):
            if result["input"][field] != manifest_sample[field]:
                raise ValueError(f"result sample {field} does not match manifest: {sample_id}")
        sample_ids.append(sample_id)
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("sample result identifiers must be unique")


def _aggregate_edit_rate(samples: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
    values = [sample["metrics"][key] for sample in samples if sample["metrics"] and sample["metrics"][key]]
    distance = sum(value["edit_distance"] for value in values)
    units = sum(value["reference_units"] for value in values)
    return {
        "evaluated_samples": len(values), "edit_distance": distance,
        "reference_units": units, "rate": distance / units if units else None,
    }


def _aggregate_keyword(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [sample["metrics"]["keyword"] for sample in samples if sample["metrics"] and sample["metrics"]["keyword"]]
    hits = sum(1 for value in values if value["all_hit"])
    return {"evaluated_samples": len(values), "hit_samples": hits, "sample_hit_rate": hits / len(values) if values else None}


def _aggregate_silence(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [sample["metrics"]["silence"] for sample in samples if sample["metrics"] and sample["metrics"]["silence"]]
    false_count = sum(1 for value in values if value["false_recognition"])
    return {"evaluated_samples": len(values), "false_recognition_samples": false_count, "false_recognition_rate": false_count / len(values) if values else None}


def _aggregate_realtime_factor(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [sample["metrics"]["realtime_factor"] for sample in samples if sample["metrics"]]
    return {
        "evaluated_samples": len(values),
        "mean_realtime_factor": sum(values) / len(values) if values else None,
        "max_realtime_factor": max(values) if values else None,
    }


def _display(value: Any) -> str:
    return "n/a" if value is None else f"{value:.6f}" if isinstance(value, float) else str(value)


def _cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")
