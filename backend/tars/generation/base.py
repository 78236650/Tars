"""TARS Generation - 图像/视频生成统一抽象"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GenResult:
    """生成结果"""
    success: bool
    url: Optional[str] = None           # 公网 URL（图片 / 视频）
    base64: Optional[str] = None        # base64 data URL（小图可嵌入）
    task_id: Optional[str] = None       # 异步任务 ID（视频生成）
    error: Optional[str] = None
    # 视频异步状态
    status: str = "completed"           # completed / processing / failed
    metadata: dict = field(default_factory=dict)


class BaseGenProvider(ABC):
    """生成 Provider 抽象基类"""

    @abstractmethod
    async def generate_image(
        self, prompt: str, negative_prompt: str = "",
        width: int = 1024, height: int = 1024, **kwargs
    ) -> GenResult:
        """生成图片，返回 GenResult"""
        ...

    @abstractmethod
    async def generate_video(
        self, prompt: str, duration: int = 5,
        width: int = 832, height: int = 480, **kwargs
    ) -> GenResult:
        """生成视频（异步），返回 GenResult(task_id=...)"""
        ...

    async def poll_video(self, task_id: str) -> GenResult:
        """轮询视频生成状态（默认不支持，子类覆盖）"""
        return GenResult(success=False, error="poll_video not supported by this provider")
