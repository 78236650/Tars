"""Agnes AI Provider - 图像 & 视频生成

Agnes AI (agnes-ai.com) 提供 OpenAI 兼容的图像/视频生成 API。
- 图像: POST /v1/images/generations  model: agnes-image-2.1-flash
- 视频: POST /v1/videos               model: agnes-video-v2.0
"""
import base64
import logging
from typing import Optional

import httpx

from ..base import BaseGenProvider, GenResult

logger = logging.getLogger(__name__)


class AgnesProvider(BaseGenProvider):
    """Agnes AI 图像和视频生成 Provider"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://apihub.agnes-ai.com/v1",
        image_model: str = "agnes-image-2.1-flash",
        video_model: str = "agnes-video-v2.0",
        timeout: int = 120,
        poll_interval: int = 5,
        max_polls: int = 36,  # 最多等 3 分钟
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.image_model = image_model
        self.video_model = video_model
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_polls = max_polls

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _download_as_base64(self, url: str) -> Optional[str]:
        """下载图片并转为 base64 data URL"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                b64 = base64.b64encode(resp.content).decode("ascii")
                content_type = resp.headers.get("content-type", "image/png")
                return f"data:{content_type};base64,{b64}"
        except Exception as e:
            logger.warning(f"download base64 failed: {e}")
            return None

    # ── Image ────────────────────────────────────────────

    async def generate_image(
        self, prompt: str, negative_prompt: str = "",
        width: int = 1024, height: int = 1024, **kwargs
    ) -> GenResult:
        size = f"{width}x{height}"
        if width not in (256, 512, 768, 1024, 1440, 1792) or height not in (256, 512, 768, 1024, 1440, 1792):
            # Agnes 兼容 OpenAI size 约束
            size = "1024x1024"

        payload = {
            "model": self.image_model,
            "prompt": prompt,
            "n": 1,
            "size": size,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/images/generations",
                    headers=self._headers(),
                    json=payload,
                )
                data = resp.json()

            if resp.status_code == 200:
                items = data.get("data") or []
                if items:
                    url = items[0].get("url")
                    if not url:
                        return GenResult(success=False, error="API returned no image URL")
                    # 下载并转为 base64，前端可直接渲染
                    b64 = await self._download_as_base64(url)
                    return GenResult(
                        success=True,
                        url=url,
                        base64=b64,
                        metadata={"model": self.image_model, "size": size},
                    )
                return GenResult(success=False, error="API returned empty data array")
            else:
                error_msg = data.get("error", {}).get("message", str(data))
                return GenResult(success=False, error=error_msg)
        except Exception as e:
            logger.exception("Agnes image gen failed")
            return GenResult(success=False, error=str(e))

    # ── Video ────────────────────────────────────────────

    async def generate_video(
        self, prompt: str, duration: int = 5,
        width: int = 832, height: int = 480, **kwargs
    ) -> GenResult:
        payload = {
            "model": self.video_model,
            "prompt": prompt,
            "size": f"{width}x{height}",
            "duration": duration,
            "n": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/videos",
                    headers=self._headers(),
                    json=payload,
                )
                data = resp.json()

            if resp.status_code == 200:
                task_id = data.get("id") or data.get("task_id")
                if not task_id:
                    return GenResult(success=False, error="API returned no task_id")
                return GenResult(
                    success=True,
                    task_id=task_id,
                    status="processing",
                    metadata={"model": self.video_model, "duration": duration},
                )
            else:
                error_msg = data.get("error", {}).get("message", str(data))
                return GenResult(success=False, error=error_msg)
        except Exception as e:
            logger.exception("Agnes video gen failed")
            return GenResult(success=False, error=str(e))

    async def poll_video(self, task_id: str) -> GenResult:
        """轮询视频任务状态"""
        for attempt in range(self.max_polls):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        f"{self.base_url}/videos/{task_id}",
                        headers=self._headers(),
                    )
                    data = resp.json()

                if resp.status_code != 200:
                    return GenResult(
                        success=False, task_id=task_id,
                        error=f"Poll failed: {data}",
                    )

                status = data.get("status", "")
                if status == "completed":
                    url = data.get("url") or data.get("video_url") or ""
                    thumb = data.get("thumbnail_url") or ""
                    return GenResult(
                        success=True,
                        url=url,
                        status="completed",
                        task_id=task_id,
                        metadata={"thumbnail": thumb, "model": self.video_model},
                    )
                elif status in ("failed", "error", "cancelled"):
                    return GenResult(
                        success=False, task_id=task_id,
                        error=data.get("error", "Video generation failed"),
                        status="failed",
                    )
                # else: processing
                await _async_sleep(self.poll_interval)
            except Exception as e:
                logger.warning(f"poll video attempt {attempt} failed: {e}")
                await _async_sleep(self.poll_interval)

        return GenResult(
            success=False, task_id=task_id,
            error=f"Video not completed after {self.max_polls * self.poll_interval}s",
            status="processing",
        )


async def _async_sleep(seconds: float):
    """兼容不同 asyncio 运行环境"""
    import asyncio
    await asyncio.sleep(seconds)
