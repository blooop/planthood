"""Quality harness: objective metrics that define what a 'good' pipeline run looks like.

Turns the vague goal 'high-quality recipes' into checkable numbers — coverage, grounding,
dependency sanity, and timeline realism — so prompt/model changes can be measured and
regressions caught in CI.
"""

from .report import THRESHOLDS, check_thresholds, compute_report, format_report

__all__ = ["compute_report", "check_thresholds", "format_report", "THRESHOLDS"]
