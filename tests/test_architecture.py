"""复制最小源码，故意破坏架构；验证真实 Import Linter 会拒绝违规。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("module", "addition"),
    [
        ("rules", "\nfrom .service import GameService\n"),
        ("ai", "\nfrom .store import Store\n"),
        ("content", "\nfrom fastapi import FastAPI\n"),
        ("unclassified_new_module", "\nvalue = 1\n"),
    ],
)
def test_real_contracts_reject_reversed_dependencies_and_unclassified_modules(
    tmp_path, module, addition
):
    package = tmp_path / "src/langrensha"
    package.mkdir(parents=True)
    for path in (ROOT / "src/langrensha").glob("*.py"):
        shutil.copyfile(path, package / path.name)
    shutil.copyfile(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    target = package / f"{module}.py"
    target.write_text((target.read_text() if target.exists() else "") + addition)
    env = {**os.environ, "PYTHONPATH": str(tmp_path / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from importlinter.cli import lint_imports_command; lint_imports_command()",
            "--no-cache",
            "--no-logo",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "BROKEN" in result.stdout or "not listed in the layers" in result.stdout, result.stdout
