# DeepSeek 无人值守开发与验收

日期：2026-10-25（北京时间）。依据：用户本轮指示及 Issue #36。

## 范围与运行位置

使用官方 `deepseek-ai/deepseek-harness`，锁定 npm 包 `@deepseek-ai/dsh@0.2.1-rc.2` 及其依赖。模型为已实测的 `deepseek-flash`，采用 high 推理强度。开发工具配置与游戏自身的 DeepSeek 接入相互独立，不改变游戏业务功能。

本机启动入口默认工作目录为 `/workspace`，自动化任务在 `/workspace/langrensha-agent` 执行。配置使用 `danger-full-access` 与 `approval.policy: never`，用于用户要求的无人值守云端开发；这是完整文件访问权限，不能作为文件隔离承诺。禁止子 Agent 与多 Issue 并行。关闭会话日志贡献和 OTel 上传；模型请求仍包含任务所需源码和工具结果。

云环境内的进程随环境生命周期停止；跨休眠执行必须依赖宿主提供的定时器，当前没有可用的云端定时器。2026-10-25 监督者已手动停用 GitHub Actions 工作流 `DeepSeek 每小时验收与串行开发`（ID 395627924，状态 `disabled_manually`），本项 GitHub 调度已撤销，不得重新启用。它原本只做状态验收，且不表示聊天助手每小时重新上线或已完成人工业务验收。

Codex 原生 Scheduled tasks 目前只能由 ChatGPT 桌面应用创建和管理；桌面应用可在本地项目目录中按小时运行，但要求电脑保持开机且应用运行。CLI 与 IDE 不提供 Scheduled 管理界面。当前云环境没有桌面应用或显示会话，Codex CLI 的 `codex exec` 又因登录令牌 401 无法运行；app-server 协议只在插件详情中出现 `ScheduledTaskSummary`，未发现创建或运行定时任务的方法。因此本环境不能创建或运行原生定时任务；仅写 `automation.toml` 不构成创建或运行证据。详见“调度现状与限制”。

## 安装与本机入口

需要 Node.js 24.9+、Python 3.12、Git、GitHub CLI。仓库内执行：

```bash
npm ci --prefix .github/deepseek-harness
python .github/scripts/启动DeepSeek.py
# 一次性无人值守任务；默认目录仍为 /workspace
python .github/scripts/启动DeepSeek.py --profile headless '读取项目规范并汇报当前阶段'
```

默认启动 Web UI，地址为 `http://127.0.0.1:3080`，不自动打开浏览器。首次进入 UI 时添加并选择 `/workspace` 或其项目目录；无界面入口不需要选择 UI 工作区。不要在没有认证代理时把完整权限的 UI 暴露到公网。

密钥优先从启动环境 `DEEPSEEK_API_KEY` 读取。本机后备路径为仓库外 `~/.config/deepseek-harness/credentials.json`，文件权限 `0600`；JSON 字段名为 `DEEPSEEK_API_KEY`，不在文档记录值。home 位于 `~/.local/state/deepseek-harness`，日志与会话只留在私密临时目录，不上传为公开附件。

## 调度现状与限制（2026-10-25 核实）

| 项目 | 事实 |
| --- | --- |
| GitHub Actions | 工作流 ID 395627924 为 `disabled_manually`；调度已由监督者撤销，不得重新启用。 |
| GitHub Secrets | 调度停用后不再需要维护 Actions Secrets；不要把“已配置密钥”当作定时任务可用的证据。 |
| Codex 原生 Scheduled | 官方文档说明 CLI/IDE 不提供 Scheduled 管理；需 ChatGPT 桌面应用，且电脑开机、应用运行、项目在磁盘可用。 |
| 当前云环境 | 无桌面应用和显示会话；`codex exec` 返回 401，令牌无法刷新；app-server 协议只有插件 `ScheduledTaskSummary` 字段，未发现创建/运行方法。不能创建或运行原生定时任务。 |
| DSH 本地服务 | Web 服务监听 `127.0.0.1:3080`，在线但空闲不等同于正在开发；headless 只在被赋予一次性任务时运行。 |

官方依据：[Scheduled tasks](https://learn.chatgpt.com/docs/automations)（其中明确 CLI 不提供 Scheduled 管理界面）。本环境不另写替代定时平台，也不通过代理、重登或读取认证文件绕过限制。

用户完成原生定时任务所需的最少操作：在一台保持开机、且本地能访问该仓库目录的电脑上打开 ChatGPT 桌面应用并登录，选择该项目目录，创建每小时运行的 Scheduled task，确认首轮实际运行。若项目只存在于当前云环境、或没有该桌面应用，则没有官方支持的原生本地定时方案，应如实保留阻塞。

原先为 Actions 准备的 Secrets 表和历史调度说明不再代表当前状态；只有维护者另行明确授权并重新启用工作流时才需要重新核对。任何情况下都不得把“仅创建 automation.toml”或“Web 服务在线”报告为定时任务已创建或已运行。

## 本机运行事实（2026-10-25 核实）

- 默认工作区：DSH workspace 存储只记录 `/workspace`，Web 与 headless 进程的工作目录均为 `/workspace`。
- 本地 Web 服务：`127.0.0.1:3080` 正在监听，未认证请求返回 401，说明服务在线且要求认证；它处于空闲状态，在线本身不是开发进度。
- 运行时密钥：启动入口 `启动DeepSeek.py` 在环境变量缺失时读取仓库外 `~/.config/deepseek-harness/credentials.json`（权限 `0600`，字段非空）；本文不记录密钥值。仓库内未发现该凭据文件。
- 当前 headless 进程：只承载本次一次性核查任务，没有业务开发任务；进程结束即停止，不能据此声称“持续开发”。
- 游戏本地服务：`127.0.0.1:8000` 返回 200，只是本地运行；游戏部署与线上验收由监督者进行，不在本项范围。

## 串行执行与审查

以下规则适用于维护者手动运行监督脚本，或未来另行获得明确授权的调度；当前没有自动调度触发它。

1. 维护者确认 Issue 的需求、正式设计、范围和验收口径，再加 `deepseek-ready` 标签。不把所有开放 Issue 视为已授权编码。用户服务器部署 #14 缺少连接信息，不自动标记。
2. 同一时间只运行一个监督实例；存在任意开放 PR 时不领取下一项。`deepseek-active` 记录唯一当前 Issue；多个活动标签或多个 PR 时暂停。
3. 从 `main` 建立 `deepseek/issue-编号` 分支。模型读取项目文档并修改、验证；监督脚本负责提交与 PR，模型子进程移除 GitHub token 环境变量。任务不能自动修改规范、自动化控制文件或执行合并、tag、Release、服务器部署。
4. Harness 单次最多 30 分钟，单次监督最多 45 分钟。异常或无改动时保留活动 Issue，不开启下一任务。无改动时还会标记 `deepseek-blocked`，停止重复花费模型预算；维护者补齐依据后移除此标签继续。临时日志不作为公开附件；任务范围过大或反复超时时需维护者缩小范围。
5. DSH 默认在 PR 正文用 `Refs #编号` 引用任务并附模型验证报告，不自行断言完整交付或添加关闭声明；维护者核实验收后再关闭 Issue。PR 还必须声明唯一 `Issue: #编号`，写清范围、实际正式依据与逐项验收证据。提交 PR 后给 Issue 添加 `deepseek-awaiting-acceptance`，合并或关闭 PR 后也不会重新实施同一任务。监督脚本对每个 head SHA 仅发送一次 `@codex review`。评论先经仓库 300 汉字限制校验。
   Codex 按根 AGENTS.md 的 Code review guidelines 读取真实 Issue、正式依据、diff 与验收证据；仓库不另设 Issue 关联 CI。发送 review 请求本身不算通过。
6. 后续人工触发检查当前 PR；收到 Codex 发现或失败 CI 时只修订当前分支，推送后重新请求最新提交审查。其余等待状态不运行模型、不领取下一问题。
7. 验收仅接受 `chatgpt-codex-connector[bot]` 发布的结构化审查状态，要求 SHA 与当前 PR head 一致、审查 completed 且无发现或未解决发现。旧提交结果、普通用户仿冒评论、仅有触发评论均不通过。所有已报告 CI 检查必须成功，且不得有失败的 commit status。
8. 不自动合并、关闭 Issue、打 tag 或发布。验收报告通过仅表示具备进入维护者验收的条件；维护者按项目规范完成实际验收和合并，功能版本的 tag/图仍按既有规范处理。`deepseek-active` 在 Issue 关闭后仍保留，持续阻挡下一任务；维护者确认主线检查及所需版本发布均完成（或本项无需发布）后，才移除此标签。监督脚本会查询已关闭的活动 Issue，不把自动关闭等同交付完成。

## 报告与停止

监督脚本每次运行在标准输出和 `临时/DeepSeek运行/验收.json` 保存当前开放 Issue、PR、提交 SHA、CI、Codex 审查及门槛判定；该文件只含脱敏状态 JSON，不自动上传。当前 GitHub Actions 调度已停用，不再生成 Actions Summary 或 artifact。模型输出不是独立验证的事实，维护者仍须核查测试证据与 Issue 验收内容；状态检查不冒充线上验收。

暂停自动开发：移除 `deepseek-ready`/`deepseek-active` 标签，或停止手动运行监督脚本。已有 PR 会继续阻挡后续任务。完全停止 GitHub 调度：保持工作流 395627924 为 `disabled_manually`，不重新启用。本机 UI 可向启动进程发送 SIGTERM。凭据到期、预算不足、网络失败、Codex 未启用或审查未完成均如实显示阻塞，不能跳过审查。

部署时的真实冒烟验证：Harness 使用 `deepseek-flash` 调用工具，读取 `/workspace/langrensha-agent/AGENTS.md` 第一行并确认工作目录 `/workspace`，退出码 0。该验证只证明 Harness 和工具链可运行，不代表后续业务 Issue 已验收。
