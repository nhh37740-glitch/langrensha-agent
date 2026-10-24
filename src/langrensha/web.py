"""真人认证边界及逐窗口 AI 推进；部署时使用单个 Uvicorn worker。"""

import hashlib
import os
import secrets
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .content import PERSONAS
from .full_game import pending
from .presentation import present
from .rules import Rejected, Role
from .service import GameService

COOKIE = "mist_session"


def create_app(
    *, database="临时/完整对局/对局.sqlite3", access_token=None, runner=None, secure=False
):
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    service = GameService(database)
    with service.store.transaction() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS web_sessions (
            digest TEXT PRIMARY KEY, game_id TEXT, seat INTEGER NOT NULL DEFAULT 1)""")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service
    advance_lock = threading.Lock()

    @app.middleware("http")
    async def boundary(request, call_next):
        if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
            origin = request.headers.get("origin")
            expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if request.headers.get("x-mist-request") != "1" or (origin and origin != expected):
                return Response(status_code=403)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return Response(status_code=415)
            # 读取上限也适用于无 Content-Length 的分块请求。
            data = bytearray()
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data) > 20000:
                    return Response(status_code=413)
            request._body = bytes(data)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        )
        return response

    def login(request):
        token = request.cookies.get(COOKIE, "")
        digest = hashlib.sha256(token.encode()).hexdigest()
        with service.store.transaction() as db:
            row = db.execute(
                "SELECT game_id,seat FROM web_sessions WHERE digest=?", (digest,)
            ).fetchone()
        if row is None:
            raise HTTPException(401, "请先进入钟楼。")
        return digest, row

    def session(request):
        _, (game_id, seat) = login(request)
        if game_id is None:
            raise HTTPException(404, "尚未启程。")
        return service.bind_player(game_id, seat)

    def safe_query(player, data):
        if not isinstance(data, dict) or set(data) != {"name", "payload"}:
            raise HTTPException(422, "请检查询问的内容。")
        try:
            retrieved = player.query(data["name"], data["payload"])
            if runner is not None and getattr(runner, "model", None) is not None:
                from .assistant import assist

                return assist(runner.model, data["name"], data["payload"], retrieved)
            return retrieved
        except Rejected as exc:
            raise HTTPException(422, "现有线索无法支持这次询问。") from exc

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.3.0"}

    @app.post("/api/enter")
    async def enter(request: Request, response: Response):
        data = await request.json()
        if (
            not isinstance(data, dict)
            or set(data) != {"password"}
            or not isinstance(data["password"], str)
        ):
            raise HTTPException(422, "请检查入镇口令。")
        if access_token and not secrets.compare_digest(
            data["password"].encode(), access_token.encode()
        ):
            raise HTTPException(403, "入镇口令不符。")
        try:
            login(request)
            return {"entered": True}
        except HTTPException:
            pass
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with service.store.transaction() as db:
            db.execute("INSERT INTO web_sessions(digest) VALUES (?)", (digest,))
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            secure=secure,
            samesite="strict",
            max_age=60 * 60 * 24 * 30,
        )
        return {"entered": True}

    @app.post("/api/game")
    async def new_game(request: Request):
        digest, _ = login(request)
        data = await request.json()
        if (
            not isinstance(data, dict)
            or set(data) != {"role"}
            or (
                data["role"] is not None
                and (
                    not isinstance(data["role"], str) or data["role"] not in {str(r) for r in Role}
                )
            )
        ):
            raise HTTPException(422, "请选择自己的身份。")
        if not advance_lock.acquire(blocking=False):
            raise HTTPException(409, "上一段故事仍在继续。")
        try:
            game_id = service.create(human_role=data["role"], full=True)
            with service.store.transaction() as db:
                db.execute("UPDATE web_sessions SET game_id=? WHERE digest=?", (game_id, digest))
            return present(service.bind_player(game_id, 1).view())
        finally:
            advance_lock.release()

    @app.get("/api/state")
    def state(request: Request):
        return present(session(request).view())

    @app.post("/api/action")
    async def action(request: Request):
        player = session(request)
        data = await request.json()
        try:
            player.submit(data)
        except Rejected as exc:
            raise HTTPException(409, "局势已变化，或这次选择无法实行。请重新查看。") from exc
        return present(player.view())

    @app.post("/api/query")
    async def ask(request: Request):
        from starlette.concurrency import run_in_threadpool

        player = session(request)
        data = await request.json()
        return await run_in_threadpool(safe_query, player, data)

    @app.post("/api/advance")
    def advance(request: Request):
        human = session(request)
        if not advance_lock.acquire(blocking=False):
            raise HTTPException(409, "旅人仍在思索。")
        try:
            view = human.view()
            snapshot = service.host_snapshot(view["game_id"])
            waiting = pending(snapshot)
            # 独立 AI 窗口；不跳过真人，也不替真人弃权。
            if waiting and view["seat"] not in waiting and not snapshot["winner"]:
                if runner is None:
                    raise HTTPException(503, "镇上的旅人尚未接通思绪，请检查服务器配置。")
                actor = waiting[0]
                from .ai import Persona

                runner.run(
                    service.bind_player(view["game_id"], actor),
                    Persona(PERSONAS[actor - 1][0], PERSONAS[actor - 1][1]),
                )
            return present(human.view())
        finally:
            advance_lock.release()

    static = Path(__file__).parent / "static"
    if (static / "assets").exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/")
    def index():
        if not (static / "index.html").exists():
            raise HTTPException(503, "网页尚未构建，请先运行 npm ci 与 npm run build。")
        return FileResponse(static / "index.html")

    @app.exception_handler(ValueError)
    async def malformed(_request, _exc):
        return Response("内容无法辨认。", status_code=422)

    return app


def main():
    import argparse

    import uvicorn
    from dotenv import load_dotenv

    from .ai import DecisionConfig, DecisionRunner, DeepSeekConfig

    parser = argparse.ArgumentParser(description="雾钟镇完整对局服务器")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    load_dotenv(override=False)
    access = os.environ.get("LANGRENSHA_ACCESS_TOKEN")
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not access:
        parser.error("远程监听必须设置 LANGRENSHA_ACCESS_TOKEN")
    runner = DecisionRunner(
        DeepSeekConfig.from_env().client(),
        DecisionConfig(max_rounds=int(os.environ.get("AI_MAX_ROUNDS", "3"))),
    )
    app = create_app(
        database=os.environ.get("LANGRENSHA_DATABASE", "临时/完整对局/对局.sqlite3"),
        access_token=access,
        runner=runner,
        secure=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
    )
    uvicorn.run(app, host=args.host, port=args.port, workers=1, access_log=False)


if __name__ == "__main__":
    main()
