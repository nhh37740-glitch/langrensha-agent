"""真实 DeepSeek 冒烟验证：只调用一次 AI 行动窗口，不对外展示私密记录。"""

import argparse
import json
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from .ai import DecisionConfig, DecisionRunner, DeepSeekConfig
from .service import GameService


def main():
    parser = argparse.ArgumentParser(description="验证 DeepSeek 原生工具调用及规则内核接入")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    try:
        provider = DeepSeekConfig.from_env()
        config = DecisionConfig(max_rounds=args.max_rounds)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    root = Path("临时/DeepSeek验证")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as directory:
        service = GameService(Path(directory) / "game.sqlite3")
        game_id = service.create(human_role="villager")
        wolf = next(
            p["seat"] for p in service.host_snapshot(game_id)["players"] if p["role"] == "wolf"
        )
        runner = DecisionRunner(provider.client(), config)
        result = runner.run(service.bind_player(game_id, wolf))
        audit = service.host_decisions(game_id)[0]
        native = [c for c in audit["calls"] if "automatic_reason" not in c]
        print(
            json.dumps(
                {
                    "模式": "DeepSeek 单窗口真实验证，仍为内核演练",
                    "模型": provider.model,
                    "模型请求轮数": result["rounds"],
                    "结束原因": result["reason"],
                    "原生工具调用次数": len(native),
                    "规则接受的原生调用": sum(c["result"]["accepted"] for c in native),
                    "普通玩家可见本次私聊": any(
                        e["kind"] == "action"
                        for e in service.bind_player(game_id, 1).view()["events"]
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if result["reason"] != "acted":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
