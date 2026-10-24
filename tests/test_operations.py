import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from langrensha.operations import (
    OperationError,
    check_configuration,
    copy_database,
    verify_database,
)
from langrensha.service import GameService
from langrensha.web import create_app

HEADERS = {"X-Mist-Request": "1"}
CONFIG = {
    "DEEPSEEK_API_KEY": "not-a-real-key",
    "LANGRENSHA_ACCESS_TOKEN": "x" * 40,
    "COOKIE_SECURE": "true",
    "SITE_ADDRESS": "mist.example.com",
}


def command(view, text):
    return {
        "request_id": str(uuid4()),
        "phase_id": view["phase_id"],
        "expected_version": view["version"],
        "tool": "wolf_chat",
        "payload": {"text": text},
    }


def test_backup_restores_sessions_receipts_and_private_game_without_later_writes(tmp_path):
    database = tmp_path / "live.sqlite3"
    app = create_app(database=database, access_token="test-access")
    with TestClient(app) as c:
        c.post("/api/enter", json={"password": "test-access"}, headers=HEADERS)
        before = c.post("/api/game", json={"role": "wolf"}, headers=HEADERS).json()
        action = command(before, "private-before-backup")
        assert c.post("/api/action", json=action, headers=HEADERS).status_code == 200
        snapshot = tmp_path / "snapshot.sqlite3"
        report = copy_database(database, snapshot)
        assert report["games"] == 1 and report["sessions"] == 1
        assert "private-before" not in json.dumps(report)
        assert snapshot.stat().st_mode & 0o777 == 0o600
        current = c.get("/api/state").json()
        c.post("/api/action", json=command(current, "after-backup"), headers=HEADERS)
        restored = tmp_path / "restored.sqlite3"
        copy_database(snapshot, restored)
        with TestClient(create_app(database=restored, access_token="test-access")) as again:
            again.cookies.update(c.cookies)
            state = again.get("/api/state").json()
            assert state["game_id"] == before["game_id"] and state["version"] == 1
            assert "private-before-backup" in json.dumps(state)
            assert "after-backup" not in json.dumps(state)
            repeated = again.post("/api/action", json=action, headers=HEADERS).json()
            assert repeated["version"] == 1
        with TestClient(create_app(database=restored)) as anonymous:
            assert anonymous.get("/api/state").status_code == 401


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "-journal"])
def test_existing_destination_and_sidecars_are_preserved(tmp_path, suffix):
    source = tmp_path / "source.sqlite3"
    GameService(source).create(full=True)
    destination = tmp_path / "out.sqlite3"
    conflict = tmp_path / (destination.name + suffix)
    conflict.write_bytes(b"keep-existing-content")
    with pytest.raises(OperationError, match="destination_exists"):
        copy_database(source, destination)
    assert conflict.read_bytes() == b"keep-existing-content"
    assert not list(tmp_path.glob(".mist-snapshot-*"))


def test_same_path_and_dangling_symlink_cannot_be_replaced(tmp_path):
    source = tmp_path / "source.sqlite3"
    GameService(source).create()
    with pytest.raises(OperationError, match="destination_exists"):
        copy_database(source, source)
    target = tmp_path / "symlink.sqlite3"
    target.symlink_to(tmp_path / "missing.sqlite3")
    with pytest.raises(OperationError, match="destination_exists"):
        copy_database(source, target)
    assert target.is_symlink()


@pytest.mark.parametrize("damage", ["invalid_bytes", "unknown_schema", "unknown_rules"])
def test_corrupt_or_unknown_database_is_not_restored(tmp_path, damage):
    source = tmp_path / "source.sqlite3"
    service = GameService(source)
    gid = service.create(full=True)
    if damage == "invalid_bytes":
        source.write_bytes(b"not a sqlite database")
    else:
        state = service.host_snapshot(gid)
        state["schema_version" if damage == "unknown_schema" else "rules"] = "future"
        with service.store.transaction() as db:
            service.store.save(db, state)
    before = source.read_bytes()
    with pytest.raises(OperationError):
        copy_database(source, tmp_path / "new.sqlite3")
    assert source.read_bytes() == before and not (tmp_path / "new.sqlite3").exists()


def test_online_writes_produce_consistent_snapshots(tmp_path):
    source = tmp_path / "live.sqlite3"
    service = GameService(source)
    gid = service.create(full=True, human_role="wolf")
    session = service.bind_player(gid, 1)
    ready = threading.Event()

    def writer():
        for i in range(60):
            session.submit(command(session.view(), f"private message {i}"))
            ready.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        job = pool.submit(writer)
        assert ready.wait(5)
        for i in range(4):
            snapshot = tmp_path / f"snapshot-{i}.sqlite3"
            copy_database(source, snapshot)
            snap = GameService(snapshot).host_snapshot(gid)
            assert len(snap["receipts"]) == snap["version"]
            assert len([e for e in snap["events"] if e["kind"] == "action"]) == snap["version"]
        job.result()
    assert service.host_snapshot(gid)["version"] == 60


def test_concurrent_backups_never_replace_each_other(tmp_path):
    source = tmp_path / "source.sqlite3"
    GameService(source).create()
    destination = tmp_path / "out.sqlite3"

    def backup():
        try:
            copy_database(source, destination)
            return "created"
        except OperationError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: backup(), range(2)))
    assert sorted(results) == ["created", "destination_exists"]
    assert verify_database(destination)["games"] == 1


def test_failure_cleans_temporary_snapshot(tmp_path, monkeypatch):
    source = tmp_path / "source.sqlite3"
    GameService(source).create()

    def fail(*args):
        raise OSError("private failure details")

    monkeypatch.setattr(os, "link", fail)
    with pytest.raises(OSError):
        copy_database(source, tmp_path / "out.sqlite3")
    assert not list(tmp_path.glob(".mist-snapshot-*"))


@pytest.mark.parametrize(
    "address", ["mist.example.com", "https://mist.example.com", "https://mist.example.com:443"]
)
def test_production_config(address):
    assert check_configuration({**CONFIG, "SITE_ADDRESS": address})["ok"]


@pytest.mark.parametrize(
    "address",
    [
        "",
        "http://mist.example.com",
        "localhost",
        "127.0.0.1",
        "https://user:pass@mist.example.com",
        "https://mist.example.com/path",
        "https://mist.example.com:8443",
    ],
)
def test_invalid_site_does_not_reveal_config_values(address):
    with pytest.raises(OperationError) as result:
        check_configuration({**CONFIG, "SITE_ADDRESS": address})
    assert result.value.fields == ["SITE_ADDRESS"]
    assert CONFIG["DEEPSEEK_API_KEY"] not in str(result.value)


def test_local_mode_is_explicit_and_invalid_fields_are_named():
    assert check_configuration({**CONFIG, "SITE_ADDRESS": "localhost"}, local=True)["ok"]
    with pytest.raises(OperationError) as result:
        check_configuration({"SITE_ADDRESS": "mist.example.com", "AI_MAX_ROUNDS": "999"})
    assert set(result.value.fields) == {
        "DEEPSEEK_API_KEY",
        "LANGRENSHA_ACCESS_TOKEN",
        "COOKIE_SECURE",
        "AI_MAX_ROUNDS",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("MIST_PROXY_SUBNET", "8.8.8.0/24"),
        ("MIST_PROXY_SUBNET", "172.30.91.0/30"),
        ("MIST_PROXY_ADDRESS", "172.30.91.1"),
        ("MIST_APPLICATION_ADDRESS", "172.30.91.2"),
        ("MIST_APPLICATION_ADDRESS", "172.31.1.3"),
    ],
)
def test_proxy_network_configuration_rejects_collisions(field, value):
    with pytest.raises(OperationError) as error:
        check_configuration({**CONFIG, field: value})
    assert field in error.value.fields


def test_audit_summary_counts_native_actions_and_fallbacks_without_private_data(tmp_path):
    from langrensha.operations import audit_summary

    service = GameService(tmp_path / "audit.sqlite3")
    gid = service.create(full=True)
    for reason in ["acted", "model_unavailable", "model_unavailable"]:
        call = {
            "tool": "abstain",
            "args": {"private": "PRIVATE-CONTENT"},
            "result": {"accepted": True, "private": "PRIVATE-RESULT"},
        }
        if reason != "acted":
            call["automatic_reason"] = reason
        service._record_decision(gid, 1, {"id": str(uuid4()), "reason": reason, "calls": [call]})
    summary = audit_summary(tmp_path / "audit.sqlite3")
    assert summary["decisions"] == 3 and summary["provider_failures"] == 2
    assert summary["provider_failure_streak"] == 2 and summary["native_accepted_calls"] == 1
    assert summary["accepted_tools"] == {"abstain": 1}
    assert "PRIVATE" not in json.dumps(summary) and gid not in json.dumps(summary)
