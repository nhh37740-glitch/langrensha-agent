"""四世界原创往事；章节作为同一世界书的检索条目使用。"""


def entries(world, public, letters):
    prefix = "world:story" if world == "mist" else f"world:{world}:story"
    rows = [
        {
            "id": f"{prefix}:{stage}",
            "title": title,
            "text": text.strip(),
            "visibility": "public",
            "chapter": {"stage": stage, "cast": cast},
        }
        for stage, (title, cast, text) in enumerate(public)
    ]
    rows.extend(
        {
            "id": f"{prefix}:letter:{role}",
            "title": title,
            "text": text.strip(),
            "visibility": [role],
            "chapter": {"stage": 1, "cast": []},
        }
        for role, (title, text) in letters.items()
    )
    return rows
