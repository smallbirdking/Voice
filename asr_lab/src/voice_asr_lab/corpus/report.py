"""Build retained corpus coverage and media quality reports."""

from __future__ import annotations

import json
import wave
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from voice_asr_lab.corpus.audio_validation import check_corpus_audio, inspect_pcm_wave
from voice_asr_lab.corpus.manifest import validate_corpus_manifest
from voice_asr_lab.corpus.preprocessing import (
    PREPROCESSING_ALGORITHM,
    TARGET_CHANNELS,
    TARGET_SAMPLE_RATE_HZ,
    TARGET_SAMPLE_WIDTH_BITS,
)


REPORT_SCHEMA_VERSION = "1.0.0"


def build_corpus_report(
    manifest: Mapping[str, Any],
    corpus_root: Path,
    derived_root: Path,
) -> dict[str, Any]:
    """Audit the complete source and derived corpus and summarize its coverage."""

    manifest_errors = validate_corpus_manifest(manifest)
    source_audit = check_corpus_audio(manifest, corpus_root)
    samples = manifest.get("samples", [])
    if not isinstance(samples, list):
        samples = []

    language_counts = Counter(
        sample.get("language") for sample in samples if isinstance(sample, Mapping)
    )
    scenario_counts = Counter(
        sample.get("scenario") for sample in samples if isinstance(sample, Mapping)
    )
    required_coverage = {
        "chinese": language_counts["zh-CN"] > 0,
        "english": language_counts["en-US"] > 0,
        "mixed_chinese_english": language_counts["zh-en"] > 0,
        "silence": scenario_counts["silence"] > 0,
        "noise": scenario_counts["noise-only"] > 0,
        "long_form": scenario_counts["long-form"] > 0,
        "short_command": scenario_counts["short-command"] > 0,
    }

    source_by_id = {sample["sample_id"]: sample for sample in source_audit["samples"]}
    report_samples: list[dict[str, Any]] = []
    errors = [f"manifest: {error}" for error in manifest_errors]
    derived_passed = 0

    for sample in samples:
        if not isinstance(sample, Mapping):
            continue
        sample_id = sample.get("sample_id", "<unknown>")
        source_report = source_by_id.get(sample_id, {})
        for error in source_report.get("errors", []):
            errors.append(f"{sample_id} source: {error}")

        derived_path = derived_root.resolve() / f"{sample_id}.wav"
        derived = _inspect_derived(sample_id, derived_path, sample.get("audio", {}))
        if derived["status"] == "passed":
            derived_passed += 1
        else:
            errors.extend(f"{sample_id} derived: {error}" for error in derived["errors"])

        reference = sample.get("reference", {})
        source_license = sample.get("source", {}).get("license", {})
        report_samples.append(
            {
                "sample_id": sample_id,
                "language": sample.get("language"),
                "scenario": sample.get("scenario"),
                "reference": {
                    "text": reference.get("text"),
                    "normalized_text": reference.get("normalized_text"),
                    "normalization_version": reference.get("normalization_version"),
                    "language_segments": reference.get("language_segments"),
                },
                "license": {
                    "identifier": source_license.get("identifier"),
                    "redistribution": source_license.get("redistribution"),
                    "evidence": source_license.get("evidence"),
                },
                "source_audio": {
                    "path": sample.get("audio", {}).get("path"),
                    "status": source_report.get("status", "failed"),
                    "facts": source_report.get("actual"),
                    "errors": source_report.get("errors", ["source audit record is missing"]),
                },
                "derived_audio": derived,
            }
        )

    missing_coverage = [name for name, covered in required_coverage.items() if not covered]
    errors.extend(f"coverage missing: {name}" for name in missing_coverage)
    restricted_samples = [
        sample["sample_id"]
        for sample in report_samples
        if sample["license"]["redistribution"] == "restricted"
    ]
    normalization_versions = sorted(
        {
            sample["reference"]["normalization_version"]
            for sample in report_samples
            if sample["reference"]["normalization_version"] is not None
        }
    )
    total_duration_ms = sum(
        sample.get("audio", {}).get("duration_ms", 0)
        for sample in samples
        if isinstance(sample, Mapping)
    )

    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "status": "passed" if not errors else "failed",
        "corpus": {
            "corpus_id": manifest.get("corpus_id"),
            "corpus_version": manifest.get("corpus_version"),
            "corpus_fingerprint": manifest.get("corpus_fingerprint"),
            "manifest_created_at": manifest.get("created_at"),
            "sample_count": len(report_samples),
            "total_duration_ms": total_duration_ms,
        },
        "validation": {
            "manifest": {"status": "passed" if not manifest_errors else "failed", "errors": manifest_errors},
            "source_audio": {
                "status": source_audit["status"],
                "passed_samples": source_audit["passed_samples"],
                "failed_samples": source_audit["failed_samples"],
            },
            "derived_audio": {
                "status": "passed" if derived_passed == len(report_samples) else "failed",
                "algorithm": PREPROCESSING_ALGORITHM,
                "required_format": {
                    "container": "wav",
                    "codec": "pcm-s16le",
                    "sample_rate_hz": TARGET_SAMPLE_RATE_HZ,
                    "channels": TARGET_CHANNELS,
                    "sample_width_bits": TARGET_SAMPLE_WIDTH_BITS,
                },
                "passed_samples": derived_passed,
                "failed_samples": len(report_samples) - derived_passed,
            },
        },
        "coverage": {
            "complete": not missing_coverage,
            "required": required_coverage,
            "language_counts": dict(sorted(language_counts.items())),
            "scenario_counts": dict(sorted(scenario_counts.items())),
        },
        "normalization": {"versions": normalization_versions},
        "licenses": {
            "restricted_sample_count": len(restricted_samples),
            "restricted_sample_ids": restricted_samples,
            "commercial_use_ready": not restricted_samples,
        },
        "samples": report_samples,
        "errors": errors,
    }


def render_corpus_report_markdown(report: Mapping[str, Any]) -> str:
    """Render the JSON report facts into a compact retained learning report."""

    corpus = report["corpus"]
    validation = report["validation"]
    coverage = report["coverage"]
    licenses = report["licenses"]
    lines = [
        "# Voice ASR v1 语料覆盖与质量报告",
        "",
        "## 结论",
        "",
        f"- 状态：`{report['status']}`",
        f"- 语料边界：`{corpus['corpus_id']}:{corpus['corpus_version']}`",
        f"- 内容指纹：`{corpus['corpus_fingerprint']}`",
        f"- 样本数：{corpus['sample_count']}；总时长：{corpus['total_duration_ms']} ms",
        f"- 源音频：{validation['source_audio']['passed_samples']}/{corpus['sample_count']} 通过",
        f"- 派生音频：{validation['derived_audio']['passed_samples']}/{corpus['sample_count']} 通过",
        f"- 规范化版本：{', '.join(report['normalization']['versions'])}",
        "",
        "## 必需覆盖",
        "",
        "| 维度 | 是否覆盖 |",
        "| --- | --- |",
    ]
    for name, covered in coverage["required"].items():
        lines.append(f"| {name} | {'是' if covered else '否'} |")

    lines.extend(
        [
            "",
            "## 样本明细",
            "",
            "| sample_id | 语言 | 场景 | 源音频 | 16kHz 派生音频 | 许可再分发 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for sample in report["samples"]:
        lines.append(
            "| {sample_id} | {language} | {scenario} | {source} | {derived} | {license} |".format(
                sample_id=_markdown_cell(sample["sample_id"]),
                language=_markdown_cell(sample["language"]),
                scenario=_markdown_cell(sample["scenario"]),
                source=_markdown_cell(sample["source_audio"]["status"]),
                derived=_markdown_cell(sample["derived_audio"]["status"]),
                license=_markdown_cell(sample["license"]["redistribution"]),
            )
        )

    lines.extend(
        [
            "",
            "## 许可边界",
            "",
            f"受限样本共 {licenses['restricted_sample_count']} 个："
            + (", ".join(f"`{sample_id}`" for sample_id in licenses["restricted_sample_ids"]) or "无")
            + "。",
            "",
            "`commercial_use_ready=false` 表示当前 v1 含 CC BY-NC 音频，仅适合本地学习和非商业评测；商用前必须替换受限样本并创建新语料版本与指纹。"
            if not licenses["commercial_use_ready"]
            else "当前清单未登记限制商用的样本。",
            "",
            "## 验证说明",
            "",
            f"派生输入统一采用 `{validation['derived_audio']['algorithm']}`：16kHz、单声道、PCM16。JSON 报告保留每个源文件和派生文件的实际摘要、帧数、时长、规范化文本、语言片段与许可证据。",
        ]
    )
    if report["errors"]:
        lines.extend(["", "## 错误", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


def write_corpus_report(
    report: Mapping[str, Any],
    json_path: Path,
    markdown_path: Path,
) -> tuple[Path, Path]:
    """Exclusively retain matching machine-readable and learning reports."""

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
        stream.write(render_corpus_report_markdown(report))
    return json_path, markdown_path


def _inspect_derived(sample_id: str, path: Path, declared_source: Any) -> dict[str, Any]:
    errors: list[str] = []
    facts: dict[str, Any] | None = None
    if not path.is_file():
        errors.append(f"derived audio does not exist: {sample_id}.wav")
    else:
        try:
            facts = inspect_pcm_wave(path)
        except (OSError, EOFError, wave.Error) as error:
            errors.append(f"unable to inspect PCM WAV: {error}")
    if facts is not None:
        expected_format = {
            "container": "wav",
            "codec": "pcm-s16le",
            "sample_rate_hz": TARGET_SAMPLE_RATE_HZ,
            "channels": TARGET_CHANNELS,
            "sample_width_bits": TARGET_SAMPLE_WIDTH_BITS,
        }
        if facts["format"] != expected_format:
            errors.append(f"format mismatch: expected {expected_format!r}, actual {facts['format']!r}")
        source_duration = declared_source.get("duration_ms") if isinstance(declared_source, Mapping) else None
        if facts["duration_ms"] != source_duration:
            errors.append(
                f"duration_ms mismatch: source {source_duration!r}, derived {facts['duration_ms']!r}"
            )
    return {
        "path": f"derived/{sample_id}.wav",
        "status": "passed" if not errors else "failed",
        "algorithm": PREPROCESSING_ALGORITHM,
        "facts": facts,
        "errors": errors,
    }


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")
