"""雾钟镇世界书适配：复用 content 中已发布的对局设定，保持来源 id 不变。"""

from ..content import GUIDANCE, PERSONAS, ROLE_NAMES, WORLD

WORLDBOOK = {
    "id": "mist",
    "name": "雾钟镇",
    "basis": "本项目原创的雾钟镇设定，沿用 content.py 中已发布的对局文案。",
    "entries": [
        {
            "id": item["id"],
            "title": item["title"],
            "text": item["text"],
            "visibility": "public",
        }
        for item in WORLD
    ],
    "roles": dict(ROLE_NAMES),
    "guidance": dict(GUIDANCE),
    "personas": list(PERSONAS),
}
