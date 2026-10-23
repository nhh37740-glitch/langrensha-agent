"""独立的内核演练命令；不是完整十二人剧本或模型对局。"""

import json
import tempfile
from pathlib import Path
from uuid import uuid4

from .service import GameService


def act(session, tool, payload):
    view = session.view()
    return session.submit(
        {
            "request_id": str(uuid4()),
            "phase_id": view["phase_id"],
            "expected_version": view["version"],
            "tool": tool,
            "payload": payload,
        }
    )


def main():
    # 演练文件遵守项目临时目录约定；退出后自动清理对局私密资料。
    root = Path("临时/内核演练")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as directory:
        service = GameService(Path(directory) / "game.sqlite3")
        game_id = service.create(human_role="villager")
        host = service.host_snapshot(game_id)
        for player in host["players"]:
            if player["role"] == "wolf":
                act(service.bind_player(game_id, player["seat"]), "wolf_vote", {"target": 1})
        for seat in range(1, 13):
            act(service.bind_player(game_id, seat), "speak", {"text": "我会留意今夜的动静。"})
        view = service.bind_player(game_id, 1).view()
        print(
            json.dumps(
                {
                    "说明": "最小内核演练；未接入特殊技能、死亡、警长、胜负和模型。",
                    "轮次": view["round"],
                    "阶段": view["phase"],
                    "公开发言数": sum(e["kind"] == "action" for e in view["events"]),
                    "普通玩家可见狼队计票": any(e["kind"] == "wolf_tally" for e in view["events"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
