"""v2.2 记忆系统配置 + Feature Flag"""
import os

from ..utils.env_helpers import get_bool_env, get_int_env, get_float_env


class MemoryConfig:
    """集中管理记忆系统运行时配置和 feature flag"""

    def __init__(self):
        # router: true 启用 MemoryRouter
        self.router_enabled = get_bool_env("TARS_MEMORY_ROUTER", True)
        self.router_fallback_on_error = get_bool_env("TARS_MEMORY_ROUTER_FALLBACK_ON_ERROR", True)

        # scene analyzer
        self.scene_model = os.getenv("TARS_SCENE_MODEL", "gemma4:e2b")
        self.scene_timeout_ms = get_int_env("TARS_SCENE_TIMEOUT", 3000)
        self.scene_cache_similarity = get_float_env("TARS_SCENE_CACHE_SIMILARITY", 0.95)

        # reflector
        self.reflector_async = get_bool_env("TARS_REFLECTOR_ASYNC", True)
        self.reflector_batch_size = get_int_env("TARS_REFLECTOR_BATCH_SIZE", 5)
        self.reflector_batch_interval_s = get_int_env("TARS_REFLECTOR_BATCH_INTERVAL_S", 30)

        # skill router: true 启用 SkillRouter
        self.skill_router_enabled = get_bool_env("TARS_SKILL_ROUTER", True)
        self.skill_top_k = get_int_env("TARS_SKILL_TOP_K", 3)
        self.skill_min_score = get_float_env("TARS_SKILL_MIN_SCORE", 0.3)

        # v4.4.0 垂直模式：周边降级开关（默认关，需要时设 env=true 打开）
        self.compressor_enabled = get_bool_env("TARS_MEMORY_COMPRESSOR", False)
        self.kb_promotion_enabled = get_bool_env("TARS_KB_PROMOTION", False)
        self.tree_builder_enabled = get_bool_env("TARS_MEMORY_TREE_BUILDER", False)
        self.turn_publisher_enabled = get_bool_env("TARS_TURN_PUBLISHER", False)


config = MemoryConfig()
