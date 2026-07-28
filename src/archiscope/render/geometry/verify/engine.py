"""Verification engine — runs all rules, collects violations, severity-sorts."""

from .rules import ALL_RULES, Severity, VerifyContext, Violation


def verify(ctx: VerifyContext, enabled_rules: list[str] | None = None) -> list[Violation]:
    """Run all enabled rules against the context. Return sorted violations."""
    violations = []
    for rule_id, (default_severity, rule_fn) in ALL_RULES.items():
        if enabled_rules and rule_id not in enabled_rules:
            continue
        try:
            result = rule_fn(ctx)
            for v in result:
                if not v.rule_id:
                    v.rule_id = rule_id
                if not v.severity:
                    v.severity = default_severity
                violations.append(v)
        except Exception as e:
            violations.append(
                Violation(
                    rule_id=rule_id,
                    severity=Severity.INFO,
                    message=f"规则执行异常: {e}",
                    subject=rule_id,
                )
            )
    return sorted(violations, key=lambda v: _severity_order(v.severity))


def _severity_order(s: Severity) -> int:
    return {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }[s]


def has_critical(violations: list[Violation]) -> bool:
    return any(v.severity == Severity.CRITICAL for v in violations)


def severity_label(s: Severity) -> str:
    return {
        Severity.CRITICAL: "🔴",
        Severity.HIGH: "🟠",
        Severity.MEDIUM: "🟡",
        Severity.LOW: "🟢",
        Severity.INFO: "🔵",
    }.get(s, "⚪")
