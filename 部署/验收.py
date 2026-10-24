"""真实本机 HTTPS/会话/备份恢复验收；只清理自己创建的随机 Compose 项目。"""

import argparse
import json
import os
import secrets
import ssl
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def available_port():
    import socket

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for(call, *, seconds=45, expected=(200,)):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            response = call()
            if response.status_code in expected:
                return response
        except (httpx.HTTPError, OSError):
            pass
        time.sleep(0.3)
    raise RuntimeError("service_not_ready")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "临时/部署验收")
    parser.add_argument("--ca-bundle", type=Path)
    parser.add_argument(
        "--real-env", type=Path, help="显式启用最多两个实际 AI 窗口，读取该私密配置"
    )
    parser.add_argument(
        "--full-game", action="store_true", help="显式启用最多 350 窗口的完整真实对局"
    )
    args = parser.parse_args()
    if args.full_game and not args.real_env:
        parser.error("--full-game 必须同时提供 --real-env")
    project = "mist-accept-" + uuid4().hex[:10]
    runtime = args.output.resolve() / project
    runtime.mkdir(parents=True, mode=0o700)
    config = runtime / "配置.env"
    os.close(os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    access = secrets.token_urlsafe(32)
    key = "ci-placeholder-no-model-calls"
    if args.real_env:
        key = dotenv_values(args.real_env, interpolate=False).get("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("real_key_not_configured")
    http_port, https_port = available_port(), available_port()
    while https_port == http_port:
        https_port = available_port()
    # 每个随机项目使用自己的私网；不改变宿主路由或代理设置。
    network_octet = 40 + int(uuid4().hex[:2], 16) % 180
    values = {
        "DEEPSEEK_API_KEY": key,
        "LANGRENSHA_ACCESS_TOKEN": access,
        "AI_MAX_ROUNDS": "3",
        "COOKIE_SECURE": "true",
        "SITE_ADDRESS": "localhost",
        "LANGRENSHA_IMAGE": args.image,
        "MIST_BIND_ADDRESS": "127.0.0.1",
        "MIST_HTTP_PORT": str(http_port),
        "MIST_HTTPS_PORT": str(https_port),
        "MIST_PROXY_SUBNET": f"172.29.{network_octet}.0/24",
        "MIST_PROXY_ADDRESS": f"172.29.{network_octet}.2",
        "MIST_APPLICATION_ADDRESS": f"172.29.{network_octet}.3",
    }
    for name, value in values.items():
        set_key(config, name, value, quote_mode="always")
    env = dict(os.environ)
    for name in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        env.pop(name, None)
    env.update(MIST_ENV_FILE=str(config), **values)
    # env 的秘密值仅传给 Docker，不输出、不作为命令行参数。
    compose = [
        "docker",
        "--host=unix:///var/run/docker.sock",
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(config),
        "-f",
        str(ROOT / "部署/compose.yaml"),
    ]
    override = runtime / "验收配置.json"
    app_override = {"healthcheck": {"interval": "1s", "timeout": "3s", "retries": 30}}
    if args.ca_bundle:
        app_override.update(
            volumes=[
                {
                    "type": "bind",
                    "source": str(args.ca_bundle.resolve()),
                    "target": "/run/mist-ca.pem",
                    "read_only": True,
                }
            ],
            environment={
                "SSL_CERT_FILE": "/run/mist-ca.pem",
                "REQUESTS_CA_BUNDLE": "/run/mist-ca.pem",
            },
        )
    override.write_text(json.dumps({"services": {"town": app_override}}))
    compose += ["-f", str(override)]
    log_path = runtime / "Docker.log"
    log_descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    report = {"project": project, "ok": False, "real_model_enabled": bool(args.real_env)}
    with os.fdopen(log_descriptor, "w") as log:

        def run(arguments, *, capture=False, check=True):
            result = subprocess.run(
                arguments,
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE if capture else log,
                stderr=log,
            )
            if result.returncode and check:
                raise RuntimeError("docker_operation_failed")
            return result.stdout or ""

        def call(path, payload, *, client, extra=None):
            return client.post(path, json=payload, headers={"X-Mist-Request": "1", **(extra or {})})

        def action(state, text):
            return {
                "request_id": str(uuid4()),
                "phase_id": state["phase_id"],
                "expected_version": state["version"],
                "tool": "wolf_chat",
                "payload": {"text": text},
            }

        try:
            report["stage"] = "configuration"
            run(compose + ["config", "--quiet"])
            run(
                compose
                + ["run", "--rm", "--no-deps", "town", "langrensha-ops", "check-config", "--local"]
            )
            report["stage"] = "containers"
            run(compose + ["up", "-d", "--no-build", "--wait"])
            run(
                compose
                + [
                    "exec",
                    "-T",
                    "proxy",
                    "caddy",
                    "validate",
                    "--config",
                    "/etc/caddy/Caddyfile",
                    "--adapter",
                    "caddyfile",
                ]
            )
            # 先请求一次，让 Caddy 为 localhost 创建自己的测试 CA 和证书。
            with httpx.Client(timeout=3) as http:
                response = wait_for(
                    lambda: http.get(
                        f"http://localhost:{http_port}/api/health", follow_redirects=False
                    ),
                    expected=(301, 308),
                )
                assert response.status_code in {301, 308}
                assert response.headers["location"].startswith("https://")
                assert "set-cookie" not in response.headers
            report["stage"] = "test_certificate"
            proxy_id = run(compose + ["ps", "-q", "proxy"], capture=True).strip()
            ca_file = runtime / "测试根证书.crt"
            run(
                [
                    "docker",
                    "--host=unix:///var/run/docker.sock",
                    "cp",
                    proxy_id + ":/data/caddy/pki/authorities/local/root.crt",
                    str(ca_file),
                ]
            )
            tls = ssl.create_default_context(cafile=str(ca_file))
            base = f"https://localhost:{https_port}"
            with (
                httpx.Client(base_url=base, verify=tls, timeout=100) as wolf,
                httpx.Client(base_url=base, verify=tls, timeout=20) as ordinary,
            ):
                report["stage"] = "https_sessions"
                health = wait_for(lambda: wolf.get("/api/health")).json()
                report["version"] = health["version"]
                assert "雾钟镇" in wolf.get("/").text
                entered = call(
                    "/api/enter",
                    {"password": access},
                    client=wolf,
                    extra={"Origin": base, "X-Forwarded-Proto": "http"},
                )
                assert entered.status_code == 200
                cookie = entered.headers["set-cookie"].lower()
                assert all(flag in cookie for flag in ("secure", "httponly", "samesite=strict"))
                rejected = call(
                    "/api/query",
                    {"name": "self_info", "payload": {}},
                    client=wolf,
                    extra={"Origin": "https://attacker.invalid"},
                )
                assert rejected.status_code == 403
                initial = call(
                    "/api/game", {"role": "wolf"}, client=wolf, extra={"Origin": base}
                ).json()
                marker = "private-" + uuid4().hex
                original_command = action(initial, marker)
                before = call("/api/action", original_command, client=wolf).json()
                assert before["version"] == 1
                call("/api/enter", {"password": access}, client=ordinary)
                public = call("/api/game", {"role": "villager"}, client=ordinary).json()
                search = call(
                    "/api/query",
                    {"name": "search_history", "payload": {"query": marker}},
                    client=ordinary,
                )
                assert search.status_code == 200 and marker not in search.text
                spoof = ordinary.get(
                    "/api/state", params={"game_id": initial["game_id"], "seat": 1}
                ).json()
                assert spoof["game_id"] == public["game_id"]
                report["stage"] = "backup_restore"
                backup = run(
                    compose
                    + [
                        "exec",
                        "-T",
                        "town",
                        "langrensha-ops",
                        "backup",
                        "--database",
                        "/data/对局.sqlite3",
                        "--output",
                        "/data/backups/验收.sqlite3",
                    ],
                    capture=True,
                )
                assert json.loads(backup)["sessions"] == 2
                late = call("/api/action", action(before, "after-backup"), client=wolf).json()
                assert late["version"] == 2
                run(
                    compose
                    + [
                        "exec",
                        "-T",
                        "town",
                        "langrensha-ops",
                        "restore",
                        "--backup",
                        "/data/backups/验收.sqlite3",
                        "--database",
                        "/data/恢复.sqlite3",
                    ]
                )
                env["MIST_DATABASE"] = "/data/恢复.sqlite3"
                run(
                    compose
                    + ["up", "-d", "--no-build", "--no-deps", "--force-recreate", "--wait", "town"]
                )
                restored = wait_for(lambda: wolf.get("/api/state")).json()
                assert restored["game_id"] == initial["game_id"] and restored["version"] == 1
                assert marker in json.dumps(restored) and "after-backup" not in json.dumps(restored)
                repeated = call("/api/action", original_command, client=wolf).json()
                assert repeated["version"] == 1
                assert ordinary.get("/api/state").json()["game_id"] == public["game_id"]
                if args.real_env:
                    report["stage"] = "real_model"
                    current = wolf.get("/api/state").json()
                    vote = {
                        "request_id": str(uuid4()),
                        "phase_id": current["phase_id"],
                        "expected_version": current["version"],
                        "tool": "wolf_vote",
                        "payload": {"target": 2},
                    }
                    assert call("/api/action", vote, client=wolf).status_code == 200
                    native_windows = 0
                    limit = 350 if args.full_game else 2
                    for window in range(limit):
                        current = wolf.get("/api/state").json()
                        if current["winner"]:
                            break
                        if any(c["tool"] == "abstain" for c in current["choices"]):
                            abstain = {
                                "request_id": str(uuid4()),
                                "phase_id": current["phase_id"],
                                "expected_version": current["version"],
                                "tool": "abstain",
                                "payload": {},
                            }
                            assert call("/api/action", abstain, client=wolf).status_code == 200
                        else:
                            assert call("/api/advance", {}, client=wolf).status_code == 200
                            native_windows += 1
                        if args.full_game and window % 10 == 0:
                            print(
                                json.dumps({"window": window + 1, "round": current["round"]}),
                                flush=True,
                            )
                    if args.full_game:
                        ending = wolf.get("/api/state").json()
                        assert ending["winner"]
                        report["complete_game"] = {
                            "winner": ending["winner"],
                            "round": ending["round"],
                            "native_windows": native_windows,
                        }
                    count_script = (
                        "import sqlite3, json, os\n"
                        "db = sqlite3.connect(os.environ['LANGRENSHA_DATABASE'])\n"
                        "reports = [json.loads(row[0]) for row in "
                        "db.execute('SELECT report FROM ai_decisions')]\n"
                        "print(json.dumps({'decisions': len(reports), "
                        "'provider_failures': sum(r['reason'] == 'model_unavailable' "
                        "for r in reports), 'accepted_tools': [c['tool'] "
                        "for r in reports for c in r['calls'] if c['result']['accepted']]}))"
                    )
                    native = json.loads(
                        run(
                            compose + ["exec", "-T", "town", "python", "-c", count_script],
                            capture=True,
                        )
                    )
                    assert native["decisions"] == native_windows and native_windows > 0
                    assert native["provider_failures"] == 0
                    report["real_model"] = native
                    run(
                        compose
                        + [
                            "exec",
                            "-T",
                            "town",
                            "langrensha-ops",
                            "backup",
                            "--database",
                            "/data/恢复.sqlite3",
                            "--output",
                            "/data/验收留档.sqlite3",
                        ]
                    )
                    town_id = run(compose + ["ps", "-q", "town"], capture=True).strip()
                    run(
                        [
                            "docker",
                            "--host=unix:///var/run/docker.sock",
                            "cp",
                            town_id + ":/data/验收留档.sqlite3",
                            str(runtime / "私密对局.sqlite3"),
                        ]
                    )
                report.update(
                    ok=True,
                    stage="completed",
                    tls="verified_with_explicit_test_ca",
                    secure_cookie=True,
                    same_origin=True,
                    private_history_isolated=True,
                    restored_sessions=2,
                    receipts_preserved=True,
                    database_backup="consistent",
                )
        except Exception as exc:
            report["failure"] = type(exc).__name__
        finally:
            run(compose + ["down", "--volumes", "--remove-orphans"], check=False)
    (runtime / "结果.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
