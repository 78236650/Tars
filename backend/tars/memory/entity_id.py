"""实体 ID 确定性哈希工具 — v2.2"""
import hashlib
import re


def compute_entity_id(entity_type: str, name: str) -> str:
    """type:md5(name)[:8] — 确定性实体 ID"""
    normalized = normalize_entity_name(name)
    h = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{entity_type}:{h}"


def normalize_entity_name(name: str) -> str:
    """规范化名称：去空白、去标点、转小写"""
    name = name.strip().lower()
    name = re.sub(r'[^\w\s]', '', name)   # 去标点
    name = re.sub(r'\s+', '_', name)      # 空白转下划线
    return name


SLUG_RE = re.compile(r'^[a-z0-9_-]+$')


def is_valid_slug(slug: str) -> bool:
    return bool(SLUG_RE.match(slug))
