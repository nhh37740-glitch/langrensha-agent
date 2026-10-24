# PR 审查操作说明

对应 #22。仓库 agent 创建或更新 PR 后，默认先请求 GitHub Copilot，所有操作通过 CLI/API，不用浏览器，不默认触发 Codex code review。GitHub 仓库/组织设置若另有自动 Codex 审查，这份流程不能关闭它，需在对应设置中管理。

## 使用前提与命令

需要已配置认证的 `gh`、仓库读取与 PR reviewer 请求权限，以及账号可用的 Copilot Code Review 资格/额度。使用现有凭据，不运行交互登录、不输出令牌。先推送 PR 的目标提交，然后运行：

```bash
python .github/scripts/请求PR审查.py 23 --repo nhh37740-glitch/langrensha-agent
```

脚本首选 `gh pr edit 23 --repo nhh37740-glitch/langrensha-agent --add-reviewer @copilot`。旧版 gh 可能在 Project GraphQL 或 reviewer 别名上失败，此时经 `gh api` 请求 `copilot-pull-request-reviewer[bot]`，不改用浏览器。报告写入忽略的 `临时/PR审查/PR-23.json`（0600）；只含仓库、PR、head、请求途径、结果及 review 链接，不复制认证信息和审查正文。

## 查询与决策

默认每 30 秒查询一次，最多 600 秒；单次 CLI 调用另有 45 秒超时。可用 `--wait-seconds 180 --interval 15` 调整，轮询间隔 5～60 秒，总等待 0～1800 秒。网络开销不含在轮询等待时间内，单次超时后不无限重试。

- `reviewed`：找到当前 head 的有效 Copilot review，退出 0；这**不代表意见已处理、线程已解决或 Actions 成功**。
- `unavailable`：本次请求后得到当前提交的不可用/额度不足通知，不算有效审查。
- `request_failed`、`metadata_unavailable`、`timed_out`：请求被拒绝、状态不可读或限时内无结果，退出 2，保留真实原因类别。
- `not_reviewable`、`head_or_state_changed`：PR 是草稿/已关闭或等待期间有新提交，重新核对 PR；不能直接沿用旧审查，也不因此自动请求第二种审查。

旧提交的 review 被忽略；请求前已有的额度失败通知不能证明本次也失败。有效结果应从报告链接或下列接口核对：

```bash
gh api --paginate repos/nhh37740-glitch/langrensha-agent/pulls/23/reviews
gh api --paginate repos/nhh37740-glitch/langrensha-agent/pulls/23/comments
gh pr checks 23 --repo nhh37740-glitch/langrensha-agent
```

逐条检查可操作意见、解决线程后，确认当前提交的五项 Actions 都成功；不能把“请求已接受”、Copilot 的额度通知或零行内评论当成审查通过。推送修复后重新请求/核对当前 head。

## 明确降级

只有用户明确要求，或本次 Copilot 不可用、请求失败、状态读取失败/超时，才记录具体事实后通过 GitHub 评论请求 `@codex review`；脚本本身不会自动请求或重复请求 Codex。记录示例：“PR 23，提交 abc123，API 请求接受，但 Copilot 返回额度不足；本次降级为 GitHub Codex。”若两者都不可用，保留 PR 待审，不绕过审核与 Actions。不要报告节省了尚未测量的 token 数量。

PR 模板分别记录 Copilot 尝试、当前有效审查与意见处理，不把降级审查谎称为 Copilot 审查。日常开发记录每条不超过 200 个汉字，详细测试与设计用正式文档链接。
