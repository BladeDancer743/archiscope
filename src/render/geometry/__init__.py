"""Archiscope geometry package."""

from .draw.grid import CharGrid, Rect, str_width, BLOCK_FULL, BLOCK_LIGHT
from .verify.engine import verify, has_critical, severity_label
from .verify.rules import VerifyContext, Violation, Severity
from .correct.engine import correct, CorrectionResult
