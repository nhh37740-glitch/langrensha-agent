"""部署配置与 SQLite 快照操作；只提供主持运维 CLI，不暴露给玩家 API。"""

import argparse
import hashlib
import ipaddress
import json
import os
import re
import sqlite3
import tempfile
import time
from collections import Counter
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit


class OperationError(ValueError):
    def __init__(self, code, fields=()):
        self.code, self.fields = code, list(fields)
        super().__init__(code)


def check_configuration(values, *, local=False):
    invalid = []
    if not values.get("DEEPSEEK_API_KEY", "").strip():
        invalid.append("DEEPSEEK_API_KEY")
    if len(values.get("LANGRENSHA_ACCESS_TOKEN", "")) < 32:
        invalid.append("LANGRENSHA_ACCESS_TOKEN")
    if values.get("COOKIE_SECURE", "").lower() != "true":
        invalid.append("COOKIE_SECURE")
    try:
        rounds = int(values.get("AI_MAX_ROUNDS", "3"))
        if not 1 <= rounds <= 20:
            raise ValueError
    except (ValueError, TypeError):
        invalid.append("AI_MAX_ROUNDS")
    address = values.get("SITE_ADDRESS", "").strip()
    try:
        parsed = urlsplit(address if "://" in address else "https://" + address)
        host = (parsed.hostname or "").encode("idna").decode()
        allowed_local = local and host in {"localhost", "127.0.0.1", "::1"}
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.port not in {None, 443}
        ):
            raise ValueError
        if not allowed_local:
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError
            labels = host.split(".")
            if (
                len(labels) < 2
                or len(host) > 253
                or not all(
                    re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", s)
                    for s in labels
                )
            ):
                raise ValueError
    except (ValueError, UnicodeError):
        invalid.append("SITE_ADDRESS")
    try:
        subnet = ipaddress.ip_network(values.get("MIST_PROXY_SUBNET", "172.30.91.0/24"))
        private_ranges = [
            ipaddress.ip_network(s) for s in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
        ]
        if (
            not isinstance(subnet, ipaddress.IPv4Network)
            or subnet.prefixlen > 29
            or not any(subnet.subnet_of(r) for r in private_ranges)
        ):
            raise ValueError
        proxy = ipaddress.ip_address(values.get("MIST_PROXY_ADDRESS", "172.30.91.2"))
        application = ipaddress.ip_address(values.get("MIST_APPLICATION_ADDRESS", "172.30.91.3"))
        reserved = {subnet.network_address, subnet.network_address + 1, subnet.broadcast_address}
        if proxy not in subnet or proxy in reserved:
            invalid.append("MIST_PROXY_ADDRESS")
        if application not in subnet or application in reserved or application == proxy:
            invalid.append("MIST_APPLICATION_ADDRESS")
    except (ValueError, TypeError):
        invalid.append("MIST_PROXY_SUBNET")
    if invalid:
        raise OperationError("invalid_configuration", invalid)
    return {"ok": True, "configuration": "valid", "local_acceptance": local}


def _read_only(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)


def _inspect(path):
    try:
        with closing(_read_only(path)) as db:
            if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise OperationError("invalid_database")
            tables = {
                row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if not {"games", "rejections", "ai_decisions"} <= tables:
                raise OperationError("invalid_database")
            count = 0
            rules = set()
            for game_id, encoded in db.execute("SELECT id,state FROM games"):
                state = json.loads(encoded)
                if (
                    state.get("id") != game_id
                    or state.get("schema_version") != 1
                    or state.get("mode") not in {"full_game", "kernel_rehearsal"}
                ):
                    raise OperationError("unsupported_game_schema")
                if state["mode"] == "full_game":
                    if state.get("rules") != "mist-v1":
                        raise OperationError("unsupported_game_rules")
                    rules.add("mist-v1")
                count += 1
            return {
                "games": count,
                "rules": sorted(rules),
                "sessions": db.execute("SELECT count(*) FROM web_sessions").fetchone()[0]
                if "web_sessions" in tables
                else 0,
                "decisions": db.execute("SELECT count(*) FROM ai_decisions").fetchone()[0],
            }
    except (sqlite3.Error, json.JSONDecodeError, AttributeError, KeyError, TypeError) as exc:
        raise OperationError("invalid_database") from exc


def verify_database(database):
    path = Path(database)
    if not path.is_file():
        raise OperationError("database_not_found")
    details = _inspect(path)
    with path.open("rb") as content:
        digest = hashlib.file_digest(content, "sha256").hexdigest()
    return {"ok": True, **details, "bytes": path.stat().st_size, "sha256": digest}


def copy_database(source, destination):
    """SQLite 一致性副本；适用于在线备份和恢复到全新路径。绝不替换现有文件。"""
    source, destination = Path(source), Path(destination).absolute()
    if not source.is_file():
        raise OperationError("database_not_found")
    for suffix in ("", "-wal", "-shm", "-journal"):
        if os.path.lexists(str(destination) + suffix):
            raise OperationError("destination_exists")
    if source.resolve() == destination.resolve():
        raise OperationError("destination_exists")
    _inspect(source)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temp_name = tempfile.mkstemp(prefix=".mist-snapshot-", dir=destination.parent)
    os.close(descriptor)
    temp = Path(temp_name)
    deadline = time.monotonic() + 30

    def progress(_status, _remaining, _total):
        if time.monotonic() > deadline:
            raise OperationError("backup_busy_timeout")

    try:
        with closing(_read_only(source)) as reader, closing(sqlite3.connect(temp)) as writer:
            reader.backup(writer, pages=128, progress=progress, sleep=0.02)
        details = verify_database(temp)
        # 临时文件与目标在同一目录，link 的排他性防止检查后出现的目标被覆盖。
        try:
            os.link(temp, destination)
        except FileExistsError as exc:
            raise OperationError("destination_exists") from exc
        return {**details, "path": str(destination)}
    finally:
        temp.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm", "-journal"):
            Path(str(temp) + suffix).unlink(missing_ok=True)


def audit_summary(database):
    """只输出固定代码与次数，不输出操作者、参数、模型正文或会话。"""
    from .full_game import TARGET_TOOLS, TEXT_TOOLS
    from .retrieval import QUERY_TOOLS

    allowed_tools = (
        TARGET_TOOLS
        | TEXT_TOOLS
        | QUERY_TOOLS
        | {"signup", "withdraw", "antidote", "reveal", "explode", "abstain"}
    )
    allowed_reasons = {"acted", "window_closed", "model_unavailable", "thinking_rounds_exhausted"}
    path = Path(database)
    if not path.is_file():
        raise OperationError("database_not_found")
    _inspect(path)
    reasons, tools = [], Counter()
    try:
        with closing(_read_only(path)) as db:
            for (encoded,) in db.execute("SELECT report FROM ai_decisions ORDER BY rowid"):
                report = json.loads(encoded)
                reason = report.get("reason")
                reasons.append(reason if reason in allowed_reasons else "unknown")
                for call in report.get("calls", []):
                    name = call.get("tool")
                    if (
                        name in allowed_tools
                        and call.get("result", {}).get("accepted") is True
                        and "automatic_reason" not in call
                    ):
                        tools[name] += 1
    except (sqlite3.Error, json.JSONDecodeError, AttributeError, TypeError) as exc:
        raise OperationError("invalid_audit") from exc
    streak = 0
    for reason in reversed(reasons):
        if reason != "model_unavailable":
            break
        streak += 1
    return {
        "ok": True,
        "decisions": len(reasons),
        "provider_failures": reasons.count("model_unavailable"),
        "provider_failure_streak": streak,
        "native_accepted_calls": sum(tools.values()),
        "accepted_tools": dict(tools),
        "reasons": dict(Counter(reasons)),
    }


def main():
    parser = argparse.ArgumentParser(description="雾钟镇部署预检与私密数据库备份恢复")
    commands = parser.add_subparsers(dest="operation", required=True)
    check = commands.add_parser("check-config")
    check.add_argument("--env-file", type=Path)
    check.add_argument("--local", action="store_true", help="仅为本机 HTTPS 验收接受 localhost")
    backup = commands.add_parser("backup")
    backup.add_argument("--database", required=True, type=Path)
    backup.add_argument("--output", required=True, type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("--backup", required=True, type=Path)
    restore.add_argument("--database", required=True, type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--database", required=True, type=Path)
    audit = commands.add_parser("audit")
    audit.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "check-config":
            if args.env_file:
                if not args.env_file.is_file():
                    raise OperationError("configuration_not_found")
                from dotenv import dotenv_values

                values = {
                    k: v or "" for k, v in dotenv_values(args.env_file, interpolate=False).items()
                }
            else:
                values = os.environ
            result = check_configuration(values, local=args.local)
        elif args.operation == "audit":
            result = audit_summary(args.database)
        elif args.operation == "verify":
            result = verify_database(args.database)
        else:
            source = args.backup if args.operation == "restore" else args.database
            target = args.database if args.operation == "restore" else args.output
            result = copy_database(source, target)
    except OperationError as exc:
        result = {"ok": False, "code": exc.code, "fields": exc.fields}
    except (OSError, sqlite3.Error):
        result = {"ok": False, "code": "file_access_failed"}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
