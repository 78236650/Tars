import logging
from tars.wiki.compiler import WikiCompiler

logger = logging.getLogger(__name__)


class WikiEventHandler:
    def __init__(self, compiler: WikiCompiler):
        self.compiler = compiler

    async def on_meeting_ended(self, transcript: str, meeting_title: str) -> None:
        logger.info("Wiki compile triggered: meeting ended — %s", meeting_title)
        await self.compiler.compile(
            source_text=transcript,
            source_label=meeting_title,
        )

    async def on_small_file_uploaded(self, text: str, file_name: str) -> None:
        logger.info("Wiki compile triggered: file upload — %s", file_name)
        await self.compiler.compile(
            source_text=text,
            source_label=f"文件上传: {file_name}",
        )
