"""Stable repository paths shared by modules at different package depths."""

from __future__ import annotations

from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = LAB_ROOT.parent
