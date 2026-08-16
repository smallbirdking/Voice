"""Minimal command-line entry point for the isolated ASR lab."""

from __future__ import annotations

import argparse
import json
import sys
import wave
from collections.abc import Sequence
from pathlib import Path

from voice_asr_lab import __version__
from voice_asr_lab.corpus.audio_validation import check_corpus_audio
from voice_asr_lab.system.baseline import (
    DEFAULT_BASELINE_OUTPUT,
    collect_environment_baseline,
    validate_environment_baseline,
    write_environment_baseline,
)
from voice_asr_lab.corpus.manifest import load_corpus_manifest, validate_corpus_manifest
from voice_asr_lab.corpus.fingerprint import compute_corpus_fingerprint
from voice_asr_lab.corpus.report import build_corpus_report, write_corpus_report
from voice_asr_lab.corpus.assets import prepare_owned_corpus_assets
from voice_asr_lab.system.host import collect_host_snapshot, validate_host_snapshot
from voice_asr_lab.core.identifiers import (
    create_run_context,
    link_record,
    validate_run_linkage,
)
from voice_asr_lab.system.nvidia import collect_nvidia_snapshot, validate_nvidia_snapshot
from voice_asr_lab.system.offline_boundary import (
    DEFAULT_CACHE_ROOT,
    DEFAULT_MANIFEST_PATH,
    prepare_synthetic_cache,
    run_offline_synthetic_smoke,
)
from voice_asr_lab.corpus.preprocessing import preprocess_corpus


DEFAULT_WORKSPACE = Path(__file__).resolve().parents[3]


def describe_scaffold() -> dict[str, object]:
    """Return the observable boundary of the initial lab scaffold."""

    return {
        "name": "voice-asr-lab",
        "version": __version__,
        "stage": "scaffold",
        "purpose": "evaluate-local-asr-providers",
        "services_started": [],
        "excluded_product_modules": [
            "gateway",
            "database",
            "recording",
            "commands",
            "devices",
            "vision",
            "client",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voice-asr-lab")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("describe", help="describe the isolated lab boundary")

    host_probe = subcommands.add_parser("probe-host", help="emit a host environment snapshot")
    host_probe.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help="workspace path whose disk is measured",
    )
    subcommands.add_parser("probe-nvidia", help="emit NVIDIA GPU and CUDA visibility")
    subcommands.add_parser(
        "demo-run-linkage",
        help="emit one run context and three records linked to its environment snapshot",
    )
    prepare_cache = subcommands.add_parser(
        "prepare-synthetic-cache",
        help="create the tiny deterministic cache fixture used by the offline smoke test",
    )
    prepare_cache.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    offline_smoke = subcommands.add_parser(
        "offline-smoke",
        help="verify cached local work completes while external Python sockets are blocked",
    )
    offline_smoke.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    offline_smoke.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    capture_baseline = subcommands.add_parser(
        "capture-baseline",
        help="collect and save one content-addressed environment baseline",
    )
    capture_baseline.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    capture_baseline.add_argument("--output", type=Path, default=DEFAULT_BASELINE_OUTPUT)
    corpus_manifest = subcommands.add_parser(
        "validate-corpus-manifest",
        help="validate corpus manifest fields and cross-field rules without reading audio",
    )
    corpus_manifest.add_argument("manifest", type=Path)
    owned_assets = subcommands.add_parser(
        "prepare-corpus-owned-assets",
        help="create deterministic silence, noise, and bilingual source assets",
    )
    owned_assets.add_argument("--source-root", type=Path, required=True)
    audio_check = subcommands.add_parser(
        "check-corpus-audio",
        help="check corpus files, digests, WAV properties, and manifest declarations",
    )
    audio_check.add_argument("manifest", type=Path)
    audio_check.add_argument(
        "--corpus-root",
        type=Path,
        help="corpus root; defaults to the parent of the manifest directory",
    )
    preprocessing = subcommands.add_parser(
        "preprocess-corpus",
        help="create deterministic 16 kHz mono PCM16 derived corpus audio",
    )
    preprocessing.add_argument("manifest", type=Path)
    preprocessing.add_argument("--corpus-root", type=Path)
    preprocessing.add_argument("--output-root", type=Path, required=True)
    fingerprint = subcommands.add_parser(
        "fingerprint-corpus-manifest",
        help="compute and compare the corpus content fingerprint",
    )
    fingerprint.add_argument("manifest", type=Path)
    report = subcommands.add_parser(
        "report-corpus",
        help="validate source and derived audio and retain v1 coverage reports",
    )
    report.add_argument("manifest", type=Path)
    report.add_argument("--corpus-root", type=Path)
    report.add_argument("--derived-root", type=Path, required=True)
    report.add_argument("--output-json", type=Path, required=True)
    report.add_argument("--output-markdown", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a side-effect-limited lab command."""

    _configure_utf8(sys.stdout)
    _configure_utf8(sys.stderr)
    arguments = build_parser().parse_args(argv)
    command = arguments.command or "describe"

    if command == "probe-host":
        snapshot = collect_host_snapshot(arguments.workspace)
        schema_errors = validate_host_snapshot(snapshot)
        if schema_errors:
            print(json.dumps({"schema_errors": schema_errors}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        payload: dict[str, object] = snapshot
    elif command == "probe-nvidia":
        snapshot = collect_nvidia_snapshot()
        schema_errors = validate_nvidia_snapshot(snapshot)
        if schema_errors:
            print(json.dumps({"schema_errors": schema_errors}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        payload = snapshot
    elif command == "demo-run-linkage":
        host_snapshot = collect_host_snapshot(DEFAULT_WORKSPACE)
        nvidia_snapshot = collect_nvidia_snapshot()
        environment_snapshot = {
            "schema_version": "1.0.0",
            "host": host_snapshot,
            "nvidia": nvidia_snapshot,
        }
        context = create_run_context(environment_snapshot)
        linked_records = [
            link_record("sample_result", {"sample_id": "linkage-demo"}, context),
            link_record("resource_sample", {"sequence": 0}, context),
            link_record("report", {"title": "linkage-demo"}, context),
        ]
        schema_errors = [
            *(f"host: {error}" for error in validate_host_snapshot(host_snapshot)),
            *(f"nvidia: {error}" for error in validate_nvidia_snapshot(nvidia_snapshot)),
            *validate_run_linkage(context, environment_snapshot, linked_records),
        ]
        if schema_errors:
            print(json.dumps({"schema_errors": schema_errors}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        payload = {
            "schema_version": "1.0.0",
            "run_context": context,
            "environment_snapshot": {
                "environment_snapshot_id": context["environment_snapshot_id"],
                "content": environment_snapshot,
            },
            "linked_records": linked_records,
            "linkage_errors": [],
        }
    elif command == "prepare-synthetic-cache":
        payload = prepare_synthetic_cache(arguments.cache_root)
    elif command == "offline-smoke":
        payload = run_offline_synthetic_smoke(arguments.cache_root, arguments.manifest)
        if payload["status"] != "passed":
            print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
    elif command == "capture-baseline":
        baseline = collect_environment_baseline(arguments.workspace)
        schema_errors = validate_environment_baseline(baseline)
        if schema_errors:
            print(json.dumps({"schema_errors": schema_errors}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        try:
            output_path = write_environment_baseline(baseline, arguments.output)
        except FileExistsError:
            print(
                json.dumps(
                    {
                        "status": "output-exists",
                        "output": str(arguments.output.resolve()),
                        "error": "existing baseline evidence was not overwritten",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
        payload = {
            "status": "saved",
            "environment_snapshot_id": baseline["environment_snapshot_id"],
            "output": str(output_path),
            "source_commit": baseline["source_control"]["head_commit"],
            "source_dirty": baseline["source_control"]["dirty"],
            "probe_errors": baseline["errors"],
        }
    elif command == "validate-corpus-manifest":
        manifest_path = arguments.manifest
        try:
            manifest = load_corpus_manifest(manifest_path)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            print(
                json.dumps(
                    {
                        "status": "invalid",
                        "manifest": str(manifest_path.resolve()),
                        "sample_count": None,
                        "errors": [f"unable to load corpus manifest: {error}"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2

        schema_errors = validate_corpus_manifest(manifest)
        payload = {
            "status": "valid" if not schema_errors else "invalid",
            "manifest": str(manifest_path.resolve()),
            "corpus_id": manifest.get("corpus_id"),
            "corpus_version": manifest.get("corpus_version"),
            "sample_count": len(manifest.get("samples", []))
            if isinstance(manifest.get("samples"), list)
            else None,
            "errors": schema_errors,
        }
        if schema_errors:
            print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
    elif command == "prepare-corpus-owned-assets":
        try:
            assets = prepare_owned_corpus_assets(arguments.source_root)
        except (OSError, ValueError, wave.Error) as error:
            print(
                json.dumps(
                    {"status": "failed", "source_root": str(arguments.source_root.resolve()), "error": str(error)},
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
        payload = {"status": "created", "source_root": str(arguments.source_root.resolve()), "assets": assets}
    elif command == "check-corpus-audio":
        manifest_path = arguments.manifest
        try:
            manifest = load_corpus_manifest(manifest_path)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            print(
                json.dumps(
                    {"status": "failed", "manifest": str(manifest_path.resolve()), "errors": [str(error)]},
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
        corpus_root = arguments.corpus_root or manifest_path.resolve().parents[1]
        payload = check_corpus_audio(manifest, corpus_root)
        payload["manifest"] = str(manifest_path.resolve())
        if payload["status"] != "passed":
            print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
    elif command == "preprocess-corpus":
        manifest_path = arguments.manifest
        try:
            manifest = load_corpus_manifest(manifest_path)
            corpus_root = arguments.corpus_root or manifest_path.resolve().parents[1]
            payload = preprocess_corpus(manifest, corpus_root, arguments.output_root)
            payload["manifest"] = str(manifest_path.resolve())
        except (OSError, json.JSONDecodeError, ValueError, wave.Error) as error:
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "manifest": str(manifest_path.resolve()),
                        "output_root": str(arguments.output_root.resolve()),
                        "errors": [str(error)],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
    elif command == "fingerprint-corpus-manifest":
        manifest_path = arguments.manifest
        try:
            manifest = load_corpus_manifest(manifest_path)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            print(
                json.dumps(
                    {"status": "failed", "manifest": str(manifest_path.resolve()), "errors": [str(error)]},
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
        computed = compute_corpus_fingerprint(manifest)
        stored = manifest.get("corpus_fingerprint")
        payload = {
            "status": "matched" if stored == computed else "mismatched",
            "manifest": str(manifest_path.resolve()),
            "corpus_id": manifest.get("corpus_id"),
            "corpus_version": manifest.get("corpus_version"),
            "stored_fingerprint": stored,
            "computed_fingerprint": computed,
            "matches": stored == computed,
        }
        if stored != computed:
            print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
    elif command == "report-corpus":
        manifest_path = arguments.manifest
        try:
            manifest = load_corpus_manifest(manifest_path)
            corpus_root = arguments.corpus_root or manifest_path.resolve().parents[1]
            report = build_corpus_report(manifest, corpus_root, arguments.derived_root)
            if report["status"] != "passed":
                print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
                return 2
            json_path, markdown_path = write_corpus_report(
                report,
                arguments.output_json,
                arguments.output_markdown,
            )
            payload = {
                "status": "saved",
                "corpus_id": report["corpus"]["corpus_id"],
                "corpus_version": report["corpus"]["corpus_version"],
                "corpus_fingerprint": report["corpus"]["corpus_fingerprint"],
                "sample_count": report["corpus"]["sample_count"],
                "coverage_complete": report["coverage"]["complete"],
                "json_report": str(json_path),
                "markdown_report": str(markdown_path),
            }
        except (OSError, json.JSONDecodeError, ValueError, wave.Error) as error:
            print(
                json.dumps(
                    {"status": "failed", "manifest": str(manifest_path.resolve()), "errors": [str(error)]},
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
    else:
        payload = describe_scaffold()


    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _configure_utf8(stream: object) -> None:
    """Emit machine-readable JSON as UTF-8 even on legacy Windows code pages."""

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
