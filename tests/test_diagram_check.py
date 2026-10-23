"""版本图发布检查必须实际发现图源、HTML 或交付凭据漂移。"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/校验版本图.py"


@pytest.fixture
def diagram(tmp_path):
    source = tmp_path / "图源.json"
    source.write_text('{"diagram_type":"architecture"}', encoding="utf-8")
    artifacts = [tmp_path / "published/图.html", tmp_path / "generated/图.html"]
    for artifact in artifacts:
        artifact.parent.mkdir()
        artifact.write_text("<html>测试图</html>", encoding="utf-8")
        receipt = {
            "schemaVersion": 1,
            "status": "current",
            "command": "deliver",
            "type": "architecture",
            "receiptId": str(uuid4()),
            "input": f"/original/{source.name}",
            "output": f"/original/{artifact.name}",
            "specification": digest(source),
            "artifact": digest(artifact),
        }
        artifact.with_suffix(".delivery.json").write_text(json.dumps(receipt), encoding="utf-8")
    return source, *artifacts


def digest(path):
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def run_check(diagram):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, diagram)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("prefix", ["/original", "C:\\工作目录", "\\\\服务器\\共享目录"])
def test_matching_html_and_receipts_pass_across_workspaces(diagram, prefix):
    source, *artifacts = diagram
    for artifact in artifacts:
        path = artifact.with_suffix(".delivery.json")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        separator = "\\" if "\\" in prefix else "/"
        receipt["input"] = prefix + separator + source.name
        receipt["output"] = prefix + separator + artifact.name
        path.write_text(json.dumps(receipt), encoding="utf-8")
    assert run_check(diagram).returncode == 0


@pytest.mark.parametrize("change", ["source", "published", "generated", "receipt", "status"])
def test_changed_published_artifact_or_receipt_fails(diagram, change):
    source, published, generated = diagram
    if change == "source":
        source.write_text('{"diagram_type":"architecture","changed":true}', encoding="utf-8")
    elif change in ("published", "generated"):
        (published if change == "published" else generated).write_text("changed", encoding="utf-8")
    else:
        path = published.with_suffix(".delivery.json")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if change == "receipt":
            receipt["artifact"]["sha256"] = "0" * 64
        else:
            receipt["status"] = "failed"
        path.write_text(json.dumps(receipt), encoding="utf-8")
    result = run_check(diagram)
    assert result.returncode != 0 and result.stderr
