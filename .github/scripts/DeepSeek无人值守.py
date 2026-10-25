"""串行监督官方 Harness；GitHub 状态为持久依据，模型不负责合并和发布。"""

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = os.environ.get("GITHUB_REPOSITORY", "nhh37740-glitch/langrensha-agent")
OUT = ROOT / "临时/DeepSeek运行"
BOT = "chatgpt-codex-connector[bot]"
READY = "deepseek-ready"
ACTIVE = "deepseek-active"
BLOCKED = "deepseek-blocked"
REQUIRED_CHECKS = {
    "Python 内核检查",
    "网页交互与完整发行包",
    "容器构建与启动",
    "文档阶段检查",
    "版本图检查",
}


def ci_passes(checks, statuses):
    names = {c["name"] for c in checks}
    return (
        REQUIRED_CHECKS <= names
        and all(c["status"] == "completed" and c["conclusion"] == "success" for c in checks)
        and (not statuses["statuses"] or statuses["state"] == "success")
    )


def run(*args, cwd=ROOT, **kwargs):
    return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True, **kwargs)


def gh(*args):
    return json.loads(run("gh", *args).stdout)


def api(path):
    text = run("gh", "api", "--paginate", f"repos/{REPO}/{path}").stdout
    decoder = json.JSONDecoder()
    pages = []
    while text.strip():
        page, end = decoder.raw_decode(text.lstrip())
        pages.append(page)
        text = text.lstrip()[end:]
    return pages


def items(path):
    return [item for page in api(path) for item in page]


def checks_at(sha):
    checks = [
        c for page in api(f"commits/{sha}/check-runs?per_page=100") for c in page["check_runs"]
    ]
    statuses = gh("api", f"repos/{REPO}/commits/{sha}/status")
    return {
        "sha": sha,
        "checks": [
            {"name": c["name"], "status": c["status"], "conclusion": c["conclusion"]}
            for c in checks
        ],
        "ci_pass": ci_passes(checks, statuses),
    }


def codex_state(comments, sha):
    """只接受官方 bot、当前 head、已完成且无发现的结构化审查结果。"""
    state = "等待 Codex 审查"
    for comment in comments:
        if comment["user"]["login"] != BOT:
            continue
        match = re.search(r"<!-- codex-review-state:v1 (.*?) -->", comment["body"], re.S)
        if not match:
            continue
        try:
            review = json.loads(match[1])["code_review"]
        except (ValueError, KeyError, TypeError):
            continue
        if review.get("commit_sha") != sha:
            continue
        if review.get("status") != "completed":
            state = "Codex 审查中"
        elif (
            review.get("has_any_findings") is False
            and review.get("has_unresolved_findings") is False
        ):
            state = "Codex 当前提交无发现"
        else:
            state = "Codex 发现待处理"
    return state


def choose(issues, prs):
    """已有 PR/活动 Issue 优先；歧义时停止而不是并行推进。"""
    active = [i for i in issues if ACTIVE in {x["name"] for x in i["labels"]}]
    if len(prs) > 1 or len(active) > 1:
        return None, "多个 PR 或活动任务，暂停领取"
    if prs:
        return None, "等待当前 PR 审查、CI 与维护者合并；不领取其他 Issue"
    if active:
        if BLOCKED in {x["name"] for x in active[0]["labels"]}:
            return None, "当前 Issue 已受阻；维护者补齐依据后移除 deepseek-blocked 再继续"
        return active[0], "继续唯一活动 Issue"
    ready = [i for i in issues if READY in {x["name"] for x in i["labels"]}]
    return (
        (min(ready, key=lambda i: i["number"]), "领取已授权 Issue")
        if ready
        else (None, "没有标记 deepseek-ready 的任务；未标记或缺少依据的任务不自动实施")
    )


def comment(number, text):
    OUT.mkdir(parents=True, exist_ok=True)
    file = OUT / "评论.md"
    file.write_text(text, encoding="utf-8")
    run("python3", ".github/scripts/校验PR评论长度.py", "--text-file", str(file))
    run("gh", "pr", "comment", str(number), "--repo", REPO, "--body-file", str(file))


def request_review(pr, comments):
    marker = f"<!-- deepseek-codex:{pr['head']['sha']} -->"
    if not any(marker in c["body"] for c in comments):
        comment(
            pr["number"], f"@codex review\n\n请审查当前提交，核对 Issue 验收与仓库规范。\n{marker}"
        )


def audit(request=False):
    issues = [i for i in items("issues?state=open&per_page=100") if "pull_request" not in i]
    prs = items("pulls?state=open&per_page=100")
    _, selection = choose(issues, prs)
    reports = []
    for pr in prs:
        comments = items(f"issues/{pr['number']}/comments?per_page=100")
        state = codex_state(comments, pr["head"]["sha"])
        if request and state == "等待 Codex 审查":
            request_review(pr, comments)
        reports.append({"pr": pr["number"], "sha": pr["head"]["sha"], "codex": state})
    report = {
        "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "selection": selection,
        "issues": [{"number": i["number"], "title": i["title"]} for i in issues],
        "prs": reports,
        "worker_credentials": os.environ.get("HARNESS_CREDENTIALS_READY") == "true",
        "limitation": "自动状态验收不代表业务或线上验收；不自动合并、打 tag 或发布",
        "main": checks_at(gh("api", f"repos/{REPO}/commits/main")["sha"]),
    }
    for result in reports:
        result.update(checks_at(result["sha"]))
        result["gate_pass"] = result["ci_pass"] and result["codex"] == "Codex 当前提交无发现"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    summary = (
        "每小时验收\n\n```json\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```\n"
    )
    print(summary)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a", encoding="utf-8") as file:
            file.write(summary)
    return issues, prs


def worker():
    issues, prs = audit(request=True)
    issue, reason = choose(issues, prs)
    current_pr = None
    if len(prs) > 1 or sum(ACTIVE in {x["name"] for x in i["labels"]} for i in issues) > 1:
        print(reason)
        return
    if len(prs) == 1:
        pr = prs[0]
        match = re.fullmatch(r"deepseek/issue-(\d+)", pr["head"]["ref"])
        if match and pr["head"]["repo"]["full_name"] == REPO:
            current_pr = pr
            issue = next((i for i in issues if i["number"] == int(match[1])), None)
            if issue and BLOCKED in {x["name"] for x in issue["labels"]}:
                print("当前 PR 对应 Issue 已受阻，等待维护者处理")
                return
            report = json.loads((OUT / "验收.json").read_text())["prs"][0]
            failing = any(
                c["conclusion"] in {"failure", "timed_out", "cancelled"} for c in report["checks"]
            )
            if report["codex"] != "Codex 发现待处理" and not failing:
                print("当前 PR 等待 CI/Codex/维护者合并；不启动新任务")
                return
    print(reason)
    if not issue:
        return
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，未启动模型")
    if run("git", "status", "--porcelain").stdout:
        raise RuntimeError("工作区存在未提交文件，停止以保护现有修改")
    number = issue["number"]
    branch = f"deepseek/issue-{number}"
    run("gh", "issue", "edit", str(number), "--repo", REPO, "--add-label", ACTIVE)
    run("git", "fetch", "origin", "main")
    remote = run("git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}").stdout
    if remote:
        run("git", "fetch", "origin", branch)
        run("git", "checkout", "-B", branch, "FETCH_HEAD")
    else:
        run("git", "checkout", "-b", branch, "origin/main")
    instructions = (ROOT / ".github/deepseek-harness/任务指令.md").read_text()
    issue["comments_data"] = items(f"issues/{number}/comments?per_page=100")
    task = instructions + "\n本轮任务数据：\n" + json.dumps(issue, ensure_ascii=False)
    if current_pr:
        feedback = {
            "conversation": items(f"issues/{current_pr['number']}/comments?per_page=100"),
            "inline": items(f"pulls/{current_pr['number']}/comments?per_page=100"),
            "checks": report["checks"],
        }
        task += "\n当前 PR 修订数据（仅处理仍适用的问题）：\n" + json.dumps(
            feedback, ensure_ascii=False
        )
    binary = os.environ.get("DSH_BIN", str(ROOT / ".github/deepseek-harness/node_modules/.bin/dsh"))
    env = dict(os.environ)
    # 模型执行器无需 GitHub 写凭据；仅监督进程提交并推送。
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "HARNESS_GH_TOKEN"):
        env.pop(name, None)
    env.update(
        DSH_TELEMETRY_MODE="DISABLED",
        DSH_HOME=str(OUT / "home"),
        DSH_PERMISSION_MODE="danger-full-access",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    os.chmod(OUT, 0o700)
    patch = str(ROOT / ".github/deepseek-harness/无人值守.patch.yml")
    with (OUT / "模型事件.jsonl").open("w") as events, (OUT / "模型诊断.log").open("w") as log:
        proc = subprocess.Popen(
            [binary, "--profile", "headless", "--patch", patch, "--json", "-"],
            cwd=ROOT,
            env=env,
            text=True,
            stdin=subprocess.PIPE,
            stdout=events,
            stderr=log,
            start_new_session=True,
        )
        try:
            proc.communicate(task, timeout=1800)
        except subprocess.TimeoutExpired:
            import signal

            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            raise RuntimeError("Harness 超过 30 分钟，已停止；任务保持活动") from None
    events = [json.loads(line) for line in (OUT / "模型事件.jsonl").read_text().splitlines()]
    final = events[-1] if events else {}
    # 固定 rc.2 的 final 只有 text；此版本只在 turn/end completed 时以 0 退出。
    if proc.returncode or final.get("type") != "final" or not isinstance(final.get("text"), str):
        raise RuntimeError("Harness 未完成；私密日志留在临时目录，不上传")
    changed = run("git", "status", "--porcelain", "--untracked-files=all").stdout
    if not changed:
        run("gh", "issue", "edit", str(number), "--repo", REPO, "--add-label", BLOCKED)
        print("本轮无修改或任务阻塞；保留活动 Issue，不领取其他任务")
        return
    # 监督控制文件不是普通任务可修改的范围，拒绝自动提交。
    protected = [".github/", "AGENTS.md", "文档/规范/"]
    paths = run("git", "diff", "HEAD", "--name-only", "-z").stdout.split("\0")
    paths += run("git", "ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
    for path in paths:
        if any(path.startswith(p) for p in protected):
            raise RuntimeError("任务修改自动化/规范控制文件，需维护者审查；停止提交")
    run("git", "add", "--all")
    run("git", "commit", "-m", f"完成 Issue #{number} 的无人值守修改")
    run("git", "push", "origin", f"HEAD:refs/heads/{branch}")
    body = OUT / "PR.md"
    evidence = final["text"]
    for name in ("DEEPSEEK_API_KEY", "GH_TOKEN", "GITHUB_TOKEN", "HARNESS_GH_TOKEN"):
        if value := os.environ.get(name):
            evidence = evidence.replace(value, "[已脱敏]")
    body.write_text(
        f"Closes #{number}\n\n由官方 DeepSeek Harness 串行执行。"
        "实现和验证证据见提交；必须核对 Issue 验收、CI 与当前提交的 Codex review。"
        "未自动合并、发布或部署。\n\n" + str(evidence)
    )
    if current_pr:
        payload = OUT / "PR参数.json"
        payload.write_text(json.dumps({"body": body.read_text()}))
        run(
            "gh",
            "api",
            "--method",
            "PATCH",
            f"repos/{REPO}/pulls/{current_pr['number']}",
            "--input",
            str(payload),
        )
    else:
        run(
            "gh",
            "pr",
            "create",
            "--repo",
            REPO,
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            f"处理 #{number}：{issue['title']}",
            "--body-file",
            str(body),
        )
    audit(request=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", action="store_true")
    parser.add_argument("--request-review", action="store_true")
    args = parser.parse_args()
    if args.work:
        worker()
    else:
        audit(request=args.request_review)
