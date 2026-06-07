"""Transcript post-processing helpers."""

# Whisper 在静音/短音频时易复读 initial_prompt 中的指令短语
_HALLUCINATION_MARKERS = (
    "请使用简体中文",
    "简体中文标点",
    "简体中文输出",
    "以下是普通话",
    "加上合适的中文标点",
)


def filter_whisper_hallucinations(text: str, *, initial_prompt: str = "") -> str:
    """Drop lines that look like prompt-echo rather than real speech."""
    if not text:
        return ""
    prompt = (initial_prompt or "").strip()
    lines: list[str] = []
    prev = ""
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if prompt and line == prompt:
            continue
        if any(marker in line for marker in _HALLUCINATION_MARKERS) and len(line) <= 48:
            continue
        if line == prev:
            continue
        lines.append(line)
        prev = line
    # 智能拼接：仅句末标点后保持自然停顿
    return "".join(
        (l if (l.endswith("。") or l.endswith("！") or l.endswith("？") or l.endswith(".") or l.endswith("!") or l.endswith("?"))
         else l + " ")
        for l in lines
    )


def normalize_transcript_text(text: str, *, to_simplified: bool = True) -> str:
    """Whisper / mixed engines may emit Traditional Chinese — normalize to Simplified."""
    if not text or not to_simplified:
        return text
    try:
        import zhconv

        return zhconv.convert(text, "zh-hans")
    except ImportError:
        try:
            from opencc import OpenCC

            return OpenCC("t2s").convert(text)
        except ImportError:
            return text
