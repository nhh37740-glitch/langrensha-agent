"""仅供浏览器测试的离线服务器，不读取或使用任何 API 密钥。"""

import os
from pathlib import Path
from uuid import uuid4

import uvicorn

from langrensha.web import create_app


class OfflineRunner:
    def run(self, session, persona):
        view = session.view()
        tool, payload = "abstain", {}
        if "exile_vote" in view["tools"]:
            tool, payload = "exile_vote", {"target": min(view["targets"]["exile_vote"])}
        session.submit(
            {
                "request_id": str(uuid4()),
                "phase_id": view["phase_id"],
                "expected_version": view["version"],
                "tool": tool,
                "payload": payload,
            }
        )


if __name__ == "__main__":
    database = Path(
        os.environ.get(
            "TEST_DATABASE",
            str(Path(__file__).resolve().parents[1] / "临时/浏览器测试/对局.sqlite3"),
        )
    )
    app = create_app(database=database, runner=OfflineRunner())
    uvicorn.run(app, host="127.0.0.1", port=8001, access_log=False)
