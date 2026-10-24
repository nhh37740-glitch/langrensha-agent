"""可复现完整局验收；显式 --real 才会调用计费模型，最多指定窗口数。"""

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from uuid import uuid4

from .content import PERSONAS
from .full_game import alive, pending, wolves
from .service import GameService


def main():
    parser = argparse.ArgumentParser(description="完整对局验收")
    parser.add_argument(
        "--real", action="store_true", help="使用服务器 DeepSeek 配置，产生 API 费用"
    )
    parser.add_argument("--limit", type=int, default=350)
    parser.add_argument("--output", default="临时/完整对局验收")
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("limit 须为 1～1000")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    service = GameService(output / "对局.sqlite3")
    game_id = service.create(full=True, human_role="villager", rng=random.Random(23))
    runner = None
    if args.real:
        from dotenv import load_dotenv

        from .ai import DecisionConfig, DecisionRunner, DeepSeekConfig, Persona

        load_dotenv(".env", override=False)
        runner = DecisionRunner(DeepSeekConfig.from_env().client(), DecisionConfig(max_rounds=3))
    windows = 0
    for _ in range(args.limit):
        state = service.host_snapshot(game_id)
        if state["winner"]:
            break
        actor = pending(state)[0]
        session = service.bind_player(game_id, actor)
        view = session.view()
        if runner and actor != 1:
            runner.run(session, Persona(PERSONAS[actor - 1][0], PERSONAS[actor - 1][1]))
        else:
            # 真人测试替身只弃权；无网络验收以主持已知身份构造确定性胜利，不声称 AI 推理。
            tool, payload = "abstain", {}
            if not runner and "exile_vote" in view["tools"]:
                target = next(s for s in alive(state) if s in wolves(state))
                tool, payload = "exile_vote", {"target": target}
            session.submit(
                {
                    "request_id": str(uuid4()),
                    "phase_id": view["phase_id"],
                    "expected_version": view["version"],
                    "tool": tool,
                    "payload": payload,
                }
            )
        windows += 1
        if runner and windows % 10 == 0:
            print(json.dumps({"windows": windows, "round": state["round"]}), flush=True)
    state = service.host_snapshot(game_id)
    decisions = service.host_decisions(game_id)
    accepted = Counter(c["tool"] for d in decisions for c in d["calls"] if c["result"]["accepted"])
    report = {
        "mode": "real_deepseek" if runner else "deterministic_rule_acceptance",
        "game_id": game_id,
        "winner": state["winner"],
        "round": state["round"],
        "windows": windows,
        "model_decisions": len(decisions),
        "accepted_tools": dict(accepted),
        "public_events": sum(e["audience"] is None for e in state["events"]),
        "fallbacks": dict(Counter(d["reason"] for d in decisions if d["reason"] != "acted")),
    }
    (output / "验收结果.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if state["winner"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
