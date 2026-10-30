"""叙事章节的开放条件；只读取已经提供的玩家视图，不访问存储。"""


def reading_stage(view):
    if not view:
        return 0
    if view.get("winner"):
        return 6
    # 首夜警长竞选发生在 dawn 之前；猎人/遗言等中断阶段也不能靠名字猜昼夜。
    day = any(
        event.get("kind") == "dawn" and event.get("round") == view.get("round")
        for event in view.get("events", [])
    ) or view.get("phase") in {"day_speech", "exile_vote", "exile_pk_speech", "exile_pk_vote"}
    return min(5, max(1, int(view.get("round", 1)) * 2 - 1 + int(day)))


def unlocked(entry, view):
    return entry.get("chapter", {}).get("stage", 0) <= reading_stage(view)


def reading_for(book, view=None):
    """新访客只有公开序章；有玩家视图才提供该身份与阶段的正文。"""
    role = view.get("role") if view else None
    chapters = [
        {
            "id": entry["id"],
            "title": entry["title"],
            "text": entry["text"],
            "private": entry["visibility"] != "public",
            **entry["chapter"],
        }
        for entry in book["entries"]
        if "chapter" in entry
        and (entry["visibility"] == "public" or role in entry["visibility"])
        and unlocked(entry, view)
    ]
    return {
        "worldbook": book["id"],
        "name": book["name"],
        "stage": reading_stage(view),
        "chapters": chapters,
    }
