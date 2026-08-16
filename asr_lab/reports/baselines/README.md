# Environment baselines

This directory retains immutable, machine-readable snapshots used to identify the exact host, GPU, project, policy, dependency-lock, and source-control state behind later ASR experiments.

`environment-baseline-v1.json` is the first benchmark-machine snapshot. The capture command uses exclusive file creation and will not overwrite it. Later materially different baselines must use a new filename and keep the old evidence.
