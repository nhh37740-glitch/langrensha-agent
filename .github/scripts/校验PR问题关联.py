"""PR 必须声明唯一 Issue，并与唯一活动任务一致。只读取 GitHub 元数据。"""

import argparse
import json
import os
import re
import subprocess


def declared_issue(body):
    matches = re.findall(r"^Issue: #(\d+)\s*$", body or "", re.M)
    if len(matches) != 1:
        raise ValueError("PR 正文必须有且仅有一行 Issue: #编号")
    return int(matches[0])


def validate(pr, issue, active):
    number = declared_issue(pr.get("body"))
    if not issue or issue.get("number") != number or "pull_request" in issue:
        raise ValueError("对应编号不是本仓库的有效 Issue")
    if issue.get("state") != "open":
        raise ValueError("对应 Issue 已关闭，不能继续实施")
    if [i["number"] for i in active] != [number]:
        raise ValueError("PR 对应 Issue 与唯一活动任务不一致")
    branch = pr["head"]["ref"]
    if branch.startswith("deepseek/") and branch != f"deepseek/issue-{number}":
        raise ValueError("DSH 分支编号与 PR 声明的 Issue 不一致")
    closing = re.findall(
        r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)",
        pr.get("body") or "",
        re.I,
    )
    if any(int(i) != number for i in closing):
        raise ValueError("PR 不能关闭其他 Issue")
    return number


def api(path):
    text = subprocess.check_output(["gh", "api", "--paginate", path], text=True)
    pages = []
    decoder = json.JSONDecoder()
    while text.strip():
        page, end = decoder.raw_decode(text.lstrip())
        pages.append(page)
        text = text.lstrip()[end:]
    return pages


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", type=int, required=True)
    args = parser.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", "nhh37740-glitch/langrensha-agent")
    pr = api(f"repos/{repo}/pulls/{args.pr}")[0]
    number = declared_issue(pr.get("body"))
    issue = api(f"repos/{repo}/issues/{number}")[0]
    active = [
        i
        for page in api(f"repos/{repo}/issues?state=all&labels=deepseek-active&per_page=100")
        for i in page
        if "pull_request" not in i
    ]
    validate(pr, issue, active)
    print(f"PR #{args.pr} 的唯一 Issue #{number} 与活动任务一致；改动范围仍须 Codex 核查。")
