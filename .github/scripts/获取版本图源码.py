"""从长期保留的图源证据引用获取提交，不依赖可删除的功能分支或 squash 祖先。"""

import json
import re
import subprocess
import sys
from pathlib import Path


def fetch_source(candidate, archive_ref):
    revision = json.loads(candidate.read_text(encoding="utf-8"))["meta"]["repository"]["revision"]
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("图源 revision 必须是完整提交 SHA")
    if not re.fullmatch(r"refs/heads/evidence/archify-v[0-9]+\.[0-9]+\.[0-9]+", archive_ref):
        raise ValueError("只接受明确的长期图源证据分支")
    subprocess.run(["git", "fetch", "--no-tags", "origin", archive_ref], check=True)
    actual = subprocess.check_output(["git", "rev-parse", "FETCH_HEAD"], text=True).strip()
    if actual != revision:
        raise ValueError("长期证据引用与图源固定提交不一致，禁止继续校验")
    subprocess.run(["git", "cat-file", "-e", f"{revision}^{{commit}}"], check=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("用法：获取版本图源码.py <图源.json> <refs/heads/evidence/archify-v版本>")
    fetch_source(Path(sys.argv[1]), sys.argv[2])
