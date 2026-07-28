"""Archiscope geometry package."""

from .correct.engine import CorrectionResult, correct
from .draw.grid import BLOCK_FULL, BLOCK_LIGHT, CharGrid, Rect, str_width
from .verify.engine import has_critical, severity_label, verify
from .verify.rules import Severity, VerifyContext, Violation
