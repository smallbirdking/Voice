# Environment baseline v1 learning report

## Identity

- Environment snapshot ID: `env-sha256-7699e9ce6b3720ffd0eab9fa66e9244044d1d8dc85e131f49c02aca0a91dbb81`
- Captured at: `2026-08-16T13:11:57.697435Z`
- Machine-readable evidence: `environment-baseline-v1.json`
- Source commit: `1b857a3c9676aae56f1a016aa2a1230255304c91`
- Source worktree dirty at capture: `true`

The snapshot ID is the SHA-256 content address of every JSON field except the ID itself. Modifying a recorded hardware value, source state, policy digest, lock digest, timestamp, or probe result invalidates the ID.

## Observed baseline

| Area | Observation | Meaning for later ASR experiments |
| --- | --- | --- |
| Host | Windows 11, build `10.0.26200`, AMD64, 64-bit | This is the host baseline; candidate-specific WSL/container runtimes must be recorded separately. |
| CPU | Intel64 Family 6 Model 198 Stepping 2, 24 logical cores | CPU fallback and preprocessing tests can report resource use against this capacity. |
| Memory | 33,567,981,568 bytes total | Approximately 31.3 GiB physical memory; available memory is dynamic and must be sampled again per run. |
| Disk | 701,751,431,168 bytes total on the workspace volume | Model downloads must check current free space because free bytes are dynamic. |
| Python | CPython `3.14.7`, system interpreter, not a virtual environment | This scaffold has no provider dependencies; each provider still requires an isolated compatible Runtime. |
| WSL | WSL2 visible; stopped `docker-desktop` distribution | WSL exists, but this does not prove that a candidate Linux Runtime is prepared or running. |
| GPU | NVIDIA GeForce RTX 5060 Ti, 16,311 MiB | Approximately 15.9 GiB VRAM is available as the GPU capacity baseline. |
| Driver | NVIDIA `596.36`; driver-supported CUDA `13.2` | The CUDA value is driver compatibility, not an installed Toolkit version. |
| CUDA Toolkit | `not-installed`; `nvcc` absent | Provider wheels may bundle runtime libraries; real GPU execution must still be tested per isolated Runtime. |
| Network policy | `local-asr-no-cloud-audio` | Model preparation may download assets; test audio must remain on the benchmark machine. |

## Reproducibility anchors

- `uv.lock` SHA-256: `f85ec92151ebfb0c1926494ce61ec131ef35b16f1b4ad3a04fea8cd7a695857e`
- `network-policy.json` SHA-256: `f245c6691313c3112ecb04d28345daec7a947ec0ee1de8a05753f112bf21424c`
- `storage-layout.json` SHA-256: `1197bc91ce9448dcc40aa2a8c32387983b9a356eb5f8c5e5a022036176c16d31`
- Baseline validation errors: none
- Probe errors: none

The policy and lock digests matter because identical hardware does not imply an identical experiment if dependencies or local-data rules changed.

## Interpretation and limits

This is the first environment evidence, not a performance result and not a claim that any ASR provider is installable. Dynamic values such as available RAM, disk space, free VRAM, and collection timestamps will change. Later results must reference the exact snapshot ID they actually used instead of assuming this first ID remains current forever.

The capture process had permission to enumerate WSL and observed WSL2. Earlier restricted probes could see `wsl.exe` but received access denied when enumerating distributions. This difference demonstrates why the execution context belongs in evidence: future provider runs must capture the environment visible to that Runtime, especially when switching among Windows, WSL2, and containers.

The source worktree was dirty because tasks 1.6–1.8 and unrelated IDE state were not all committed when the baseline was captured. This is deliberately recorded. Before a formal cross-provider benchmark, create a new baseline from a reviewed commit and prefer `source_dirty: false`; do not edit or overwrite this historical first snapshot.

## Reproduction command

From `asr_lab/src`:

```powershell
python -m voice_asr_lab capture-baseline --output ../reports/baselines/environment-baseline-v2.json
```

Use a new filename. The command refuses to overwrite `environment-baseline-v1.json`.
