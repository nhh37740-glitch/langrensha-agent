"""世界书注册表：包内自动发现、角色可见性过滤与缺失字段回退。

本包只读取 ``content`` 中的默认数据，不依赖规则、检索、模型或存储层。
每个世界模块暴露 ``WORLDBOOK`` 字典；新增模块放入本包即可被发现，
不需要修改本文件。
"""

import importlib
import pkgutil

from ..content import GUIDANCE, ROLE_NAMES

DEFAULT_WORLD_ID = "mist"
VISIBLE_ROLES = frozenset(ROLE_NAMES)
REQUIRED_KEYS = ("id", "name", "basis", "entries", "roles", "guidance", "personas")

_WORLDBOOKS = {}


def _validate(book):
    if not isinstance(book, dict):
        raise TypeError("世界书必须是字典")
    missing = [key for key in REQUIRED_KEYS if key not in book]
    if missing:
        raise ValueError(f"世界书缺少字段：{missing}")
    for key in ("id", "name", "basis"):
        if not isinstance(book[key], str) or not book[key].strip():
            raise ValueError(f"世界书字段 {key} 必须是非空字符串")
    if not isinstance(book["entries"], list):
        raise ValueError("世界书 entries 必须是列表")
    seen = set()
    for entry in book["entries"]:
        if not isinstance(entry, dict) or not {"id", "title", "text", "visibility"} <= entry.keys():
            raise ValueError("世界书条目缺少 id/title/text/visibility")
        if not all(
            isinstance(entry[key], str) and entry[key].strip()
            for key in ("id", "title", "text")
        ):
            raise ValueError("世界书条目的 id/title/text 必须是非空字符串")
        if entry["id"] in seen:
            raise ValueError(f"世界书条目 id 重复：{entry['id']}")
        seen.add(entry["id"])
        # 雾钟镇沿用历史 world:arrival 等来源 id，其他世界必须带自己的命名空间。
        prefix = "world:" if book["id"] == DEFAULT_WORLD_ID else f"world:{book['id']}:"
        if not entry["id"].startswith(prefix):
            raise ValueError(f"世界书条目 id 必须以 {prefix} 开头")
        visibility = entry["visibility"]
        if visibility == "public":
            continue
        if not isinstance(visibility, list) or not visibility:
            raise ValueError(f"条目 {entry['id']} 的 visibility 非法")
        if not set(visibility) <= VISIBLE_ROLES:
            raise ValueError(f"条目 {entry['id']} 含未知角色")
    for key in ("roles", "guidance"):
        if not isinstance(book[key], dict) or not set(book[key]) <= VISIBLE_ROLES:
            raise ValueError(f"世界书 {key} 必须是已知角色到文本的映射")
        if not all(isinstance(value, str) and value.strip() for value in book[key].values()):
            raise ValueError(f"世界书 {key} 的文本必须是非空字符串")
    if not isinstance(book["personas"], (list, tuple)):
        raise ValueError("世界书 personas 必须是列表")


def _discover():
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        book = getattr(module, "WORLDBOOK", None)
        if book is None:
            raise ValueError(f"世界书模块 {module.__name__} 没有 WORLDBOOK")
        _validate(book)
        if book["id"] in _WORLDBOOKS:
            raise ValueError(f"世界书 id 重复：{book['id']}")
        _WORLDBOOKS[book["id"]] = book
    if DEFAULT_WORLD_ID not in _WORLDBOOKS:
        raise RuntimeError("缺少默认世界书 mist")


_discover()


def get_worldbook(worldbook_id=None):
    """按 id 取世界书；省略时返回默认世界 mist，未知 id 直接报错。"""
    key = DEFAULT_WORLD_ID if worldbook_id is None else worldbook_id
    if not isinstance(key, str) or key not in _WORLDBOOKS:
        raise KeyError(f"unknown worldbook: {key!r}")
    return _WORLDBOOKS[key]


def worldbook_ids():
    return tuple(sorted(_WORLDBOOKS))


def visible_entries(worldbook, role):
    """先按查看者角色过滤条目；秘密条目不会进入后续索引与排序。"""
    if isinstance(worldbook, str):
        worldbook = get_worldbook(worldbook)
    entries = []
    for entry in worldbook["entries"]:
        visibility = entry["visibility"]
        if visibility == "public" or role in visibility:
            entries.append(entry)
    return entries


def role_name(worldbook, role):
    """取世界内角色称谓；缺失时回退雾钟镇，避免提示词缺字段。"""
    if isinstance(worldbook, str):
        worldbook = get_worldbook(worldbook)
    return worldbook["roles"].get(role) or ROLE_NAMES.get(role, role)


def guidance_for(worldbook, role):
    """取世界内身份指导；缺失时回退雾钟镇，不阻断对局。"""
    if isinstance(worldbook, str):
        worldbook = get_worldbook(worldbook)
    return worldbook["guidance"].get(role) or GUIDANCE.get(role, "")


def personas_for(worldbook):
    if isinstance(worldbook, str):
        worldbook = get_worldbook(worldbook)
    return list(worldbook["personas"])
