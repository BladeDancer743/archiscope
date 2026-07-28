"""Geometry verification rules."""

from .rules import ALL_RULES, Violation, Severity, VerifyContext
from .engine import verify, has_critical, severity_label
