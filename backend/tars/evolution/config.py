"""Load evolution configuration from evolution.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class EvalGateSettings:
    improve_min: float = 0.10
    regress_max: float = -0.05


@dataclass
class PromptWritebackSettings:
    max_tuned_chars: int = 800


@dataclass
class InsightBurstSettings:
    window_days: int = 7
    min_downvotes: int = 3


@dataclass
class IngestSettings:
    save_state_every_n_turns: int = 5
    save_state_min_interval_seconds: int = 5
    optimize_async: bool = True


@dataclass
class CaseDistillationSettings:
    enabled: bool = True
    min_cases_per_cluster: int = 5
    max_skills_per_run: int = 3
    max_cases_per_skill: int = 30
    approval_required: bool = True


@dataclass
class EvolutionConfig:
    mode: str = "full"  # full | feedback_only
    eval_gate: EvalGateSettings = field(default_factory=EvalGateSettings)
    prompt_writeback: PromptWritebackSettings = field(default_factory=PromptWritebackSettings)
    insight_burst: InsightBurstSettings = field(default_factory=InsightBurstSettings)
    ingest: IngestSettings = field(default_factory=IngestSettings)
    case_distillation: CaseDistillationSettings = field(default_factory=CaseDistillationSettings)


def _config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "evolution.yaml"


def load_evolution_config(path: str | Path | None = None) -> EvolutionConfig:
    cfg_path = Path(path) if path else _config_path()
    if not cfg_path.exists():
        return EvolutionConfig()

    with open(cfg_path, encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    gate = raw.get("eval_gate") or {}
    prompt = raw.get("prompt_writeback") or {}
    burst = raw.get("insight_burst") or {}
    ingest = raw.get("ingest") or {}
    distillation = raw.get("case_distillation") or {}

    return EvolutionConfig(
        mode=str(raw.get("mode", "full")),
        eval_gate=EvalGateSettings(
            improve_min=float(gate.get("improve_min", 0.10)),
            regress_max=float(gate.get("regress_max", -0.05)),
        ),
        prompt_writeback=PromptWritebackSettings(
            max_tuned_chars=int(prompt.get("max_tuned_chars", 800)),
        ),
        insight_burst=InsightBurstSettings(
            window_days=int(burst.get("window_days", 7)),
            min_downvotes=int(burst.get("min_downvotes", 3)),
        ),
        ingest=IngestSettings(
            save_state_every_n_turns=int(ingest.get("save_state_every_n_turns", 5)),
            save_state_min_interval_seconds=int(ingest.get("save_state_min_interval_seconds", 5)),
            optimize_async=bool(ingest.get("optimize_async", True)),
        ),
        case_distillation=CaseDistillationSettings(
            enabled=bool(distillation.get("enabled", True)),
            min_cases_per_cluster=int(distillation.get("min_cases_per_cluster", 5)),
            max_skills_per_run=int(distillation.get("max_skills_per_run", 3)),
            max_cases_per_skill=int(distillation.get("max_cases_per_skill", 30)),
            approval_required=bool(distillation.get("approval_required", True)),
        ),
    )


_evolution_config: EvolutionConfig | None = None


def get_evolution_config() -> EvolutionConfig:
    global _evolution_config
    if _evolution_config is None:
        _evolution_config = load_evolution_config()
    return _evolution_config
