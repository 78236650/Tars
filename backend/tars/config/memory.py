"""v2.2 记忆系统配置 + Feature Flag"""
import os


class MemoryConfig:
    """集中管理记忆系统运行时配置和 feature flag"""

    def __init__(self):
        # router: true 启用 MemoryRouter
        self.router_enabled = os.getenv("TARS_MEMORY_ROUTER", "true").lower() == "true"
        self.router_fallback_on_error = True

        # scene analyzer
        self.scene_model = os.getenv("TARS_SCENE_MODEL", "gemma4:e2b")
        self.scene_timeout_ms = int(os.getenv("TARS_SCENE_TIMEOUT", "3000"))
        self.scene_cache_similarity = 0.95

        # reflector
        self.reflector_async = True
        self.reflector_batch_size = 5
        self.reflector_batch_interval_s = 30

        # skill router: true 启用 SkillRouter
        self.skill_router_enabled = os.getenv("TARS_SKILL_ROUTER", "true").lower() == "true"
        self.skill_top_k = 3
        self.skill_min_score = 0.3


config = MemoryConfig()
