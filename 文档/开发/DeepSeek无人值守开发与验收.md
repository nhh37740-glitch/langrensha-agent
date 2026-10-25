# DeepSeek 无人值守开发与验收

日期：2026-10-25（北京时间）。依据：用户本轮指示及 Issue #36。

## 范围与运行位置

使用官方 `deepseek-ai/deepseek-harness`，锁定 npm 包 `@deepseek-ai/dsh@0.2.1-rc.2` 及其依赖。模型为已实测的 `deepseek-flash`，采用 high 推理强度。开发工具配置与游戏自身的 DeepSeek 接入相互独立，不改变游戏业务功能。

本机启动入口默认工作目录为 `/workspace`，自动化任务在 `/workspace/langrensha-agent` 执行。配置使用 `danger-full-access` 与 `approval.policy: never`，用于用户要求的无人值守云端开发；这是完整文件访问权限，不能作为文件隔离承诺。禁止子 Agent 与多 Issue 并行。关闭会话日志贡献和 OTel 上传；模型请求仍包含任务所需源码和工具结果。

云环境内的进程随环境生命周期停止。跨休眠执行由 GitHub 托管执行器运行，不依赖当前聊天或云环境存活。Actions 每小时第 17 分钟调度（北京时间同样为每小时第 17 分钟），可能因 GitHub 调度延迟而晚到，不能保证精确整点。它执行自动状态验收，不表示聊天助手每小时重新上线或已完成人工业务验收。

## 安装与本机入口

需要 Node.js 24.9+、Python 3.12、Git、GitHub CLI。仓库内执行：

```bash
npm ci --prefix .github/deepseek-harness
python .github/scripts/启动DeepSeek.py
# 一次性无人值守任务；默认目录仍为 /workspace
python .github/scripts/启动DeepSeek.py --profile headless '读取项目规范并汇报当前阶段'
```

默认启动 Web UI，地址为 `http://127.0.0.1:3080`，不自动打开浏览器。首次进入 UI 时添加并选择 `/workspace` 或其项目目录；无界面入口不需要选择 UI 工作区。不要在没有认证代理时把完整权限的 UI 暴露到公网。

密钥优先从启动环境 `DEEPSEEK_API_KEY` 读取。本机后备路径为仓库外 `~/.config/deepseek-harness/credentials.json`，文件权限 `0600`；JSON 字段名为 `DEEPSEEK_API_KEY`，不在文档记录值。home 位于 `~/.local/state/deepseek-harness`，日志与会话只留在私密临时目录，不上传为 Actions 附件。

## GitHub 持久调度

工作流为 `.github/workflows/DeepSeek每小时验收.yml`，必须经 PR 合入默认分支后才会自动调度。维护者在仓库 Settings → Secrets and variables → Actions 保存：

| Secret | 用途 |
| --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek 模型访问 |
| `HARNESS_GH_TOKEN` | 专用 GitHub PAT 或适当的持久 App 凭据，用于分支推送、Issue、PR 与评论；须能触发 PR CI |

GitHub 凭据需要该仓库的 Contents、Issues、Pull requests 写权限及 Actions、Checks、Commit statuses 读权限。建议专用细粒度 PAT。不要复用聊天运行时短期 token，不在聊天、Issue、PR 或日志粘贴凭据。只用 `GITHUB_TOKEN` 推送通常不会触发后续 CI，且仓库可能禁止其创建 PR，因此自动开发明确要求独立 `HARNESS_GH_TOKEN`。

当前会话管理 Secrets 的接口返回 HTTP 403，故不能据此宣称凭据已配置。即使缺少 Secrets，定时验收仍使用只读 `github.token` 执行，并在摘要标记自动开发受阻。可在 Actions 手动运行，只验收为默认值；勾选 `work` 后才手动尝试开发。

## 串行执行与审查

1. 维护者确认 Issue 的需求、正式设计、范围和验收口径，再加 `deepseek-ready` 标签。不把所有开放 Issue 视为已授权编码。用户服务器部署 #14 缺少连接信息，不自动标记。
2. 只运行一个全局 `deepseek-serial` 工作流；存在任意开放 PR 时不领取下一项。`deepseek-active` 记录唯一当前 Issue；多个活动标签或多个 PR 时暂停。
3. 从 `main` 建立 `deepseek/issue-编号` 分支。模型读取项目文档并修改、验证；监督脚本负责提交与 PR，模型子进程移除 GitHub token 环境变量。任务不能自动修改规范、自动化控制文件或执行合并、tag、Release、服务器部署。
4. Harness 单次最多 30 分钟，完整工作流最多 45 分钟。异常或无改动时保留活动 Issue，不开启下一任务。无改动时还会标记 `deepseek-blocked`，停止重复花费模型预算；维护者补齐依据后移除此标签继续。临时日志不作为公开附件；任务范围过大或反复超时时需维护者缩小范围。
5. PR 正文包含 `Closes #编号` 与模型验证报告；监督脚本对每个 head SHA 仅发送一次 `@codex review`。评论先经仓库 300 汉字限制校验。
   PR 还必须声明唯一 `Issue: #编号`，写清范围、实际正式依据与逐项验收证据。Python CI 的“核对唯一 Issue 与活动任务”步骤验证真实 Issue、活动标签、DSH 分支及关闭关系；PR 正文编辑也会触发重查。Codex 按根 AGENTS.md 的 Code review guidelines 进一步核查实际 diff 是否符合该 Issue。每小时验收独立重查关联，不能凭旧 CI 或 PR 自述跳过。
6. 后续小时检查当前 PR；收到 Codex 发现或失败 CI 时只修订当前分支，推送后重新请求最新提交审查。其余等待状态不运行模型、不领取下一问题。
7. 验收仅接受 `chatgpt-codex-connector[bot]` 发布的结构化审查状态，要求 SHA 与当前 PR head 一致、审查 completed 且无发现或未解决发现。旧提交结果、普通用户仿冒评论、仅有触发评论均不通过。所有已报告 CI 检查必须成功，且不得有失败的 commit status。
8. 不自动合并、关闭 Issue、打 tag 或发布。验收报告通过仅表示具备进入维护者验收的条件；维护者按项目规范完成实际验收和合并，功能版本的 tag/图仍按既有规范处理。`deepseek-active` 在 Issue 关闭后仍保留，持续阻挡下一任务；维护者确认主线检查及所需版本发布均完成（或本项无需发布）后，才移除此标签。监督脚本会查询已关闭的活动 Issue，不把自动关闭等同交付完成。

## 报告与停止

每次运行的 Actions Summary 和 `DeepSeek每小时验收` artifact 保存当前开放 Issue、PR、提交 SHA、CI、Codex 审查及门槛判定；附件只含脱敏状态 JSON，保留 14 天。模型输出不是独立验证的事实，维护者仍须核查测试证据与 Issue 验收内容；状态检查不冒充线上验收。

暂停自动开发：移除 `deepseek-ready`/`deepseek-active` 标签或暂时移除专用 GitHub Secret。已有 PR 会继续阻挡后续任务。完全停止：在 Actions 禁用本工作流。本机 UI 可向启动进程发送 SIGTERM。凭据到期、预算不足、网络失败、Codex 未启用或审查未完成均如实显示阻塞，不能跳过审查。

部署时的真实冒烟验证：Harness 使用 `deepseek-flash` 调用工具，读取 `/workspace/langrensha-agent/AGENTS.md` 第一行并确认工作目录 `/workspace`，退出码 0。该验证只证明 Harness 和工具链可运行，不代表后续业务 Issue 已验收。
