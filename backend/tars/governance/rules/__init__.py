"""Governance rule registry."""

from tars.governance.rules.builtin import RULE_REGISTRY as _builtin_registry


def get_rule_fn(kind: str):
    fn = _builtin_registry.get(kind)
    if fn is None:
        raise ValueError(f"Unknown rule kind: {kind}. Available: {list(_builtin_registry.keys())}")
    return fn


def available_rules() -> list[str]:
    return list(_builtin_registry.keys())
