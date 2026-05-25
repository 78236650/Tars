"""加载 knowledge.yaml 配置。"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict

import yaml

_DEFAULT = {
    "enrichment": {
        "enabled": True,
        "timeout_sec": 120,
        "max_input_chars": 48000,
        "confidence_threshold": 0.6,
        "json_repair_retries": 1,
        "budget_per_doc_tokens": 30000,
        "synthetic_qa_max": 3,
        "glossary_max": 20,
        "key_facts_max": 30,
    },
    "chunking": {
        "profiles": {
            "policy": {"chunk_size": 1000, "overlap": 150},
            "proposal": {"chunk_size": 800, "overlap": 120},
            "metrics": {"chunk_size": 600, "overlap": 80},
            "generic": {"chunk_size": 900, "overlap": 120},
        }
    },
    "reindex": {
        "require_confirm_above_doc_count": 5,
        "estimate_tokens_per_doc": 8000,
    },
}


def _config_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config",
        "knowledge.yaml",
    )


@lru_cache(maxsize=1)
def load_knowledge_config() -> Dict[str, Any]:
    path = _config_path()
    if not os.path.isfile(path):
        return dict(_DEFAULT)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        cfg = dict(_DEFAULT)
        incoming = raw.get("knowledge") or raw
        for key in ("enrichment", "chunking", "reindex"):
            if key in incoming and isinstance(incoming[key], dict):
                merged = dict(cfg.get(key, {}))
                merged.update(incoming[key])
                cfg[key] = merged
        return cfg
    except Exception as e:
        print(f"[KnowledgeConfig] load failed: {e}")
        return dict(_DEFAULT)


def get_chunk_profile(doc_type: str) -> Dict[str, int]:
    cfg = load_knowledge_config()
    profiles = (cfg.get("chunking") or {}).get("profiles") or {}
    profile = profiles.get(doc_type) or profiles.get("generic") or {"chunk_size": 900, "overlap": 120}
    return {
        "chunk_size": int(profile.get("chunk_size", 900)),
        "overlap": int(profile.get("overlap", 120)),
    }


def get_enrichment_config() -> Dict[str, Any]:
    return dict(load_knowledge_config().get("enrichment") or {})


def get_reindex_config() -> Dict[str, Any]:
    return dict(load_knowledge_config().get("reindex") or {})
