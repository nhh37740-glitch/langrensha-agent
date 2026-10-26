# DeepSeek 无人值守开发与验收

日期：2026-10-25（北京时间）。依据：用户本轮指示及 Issue #36；2026-10-26 按 Issue #73 更新为单人串行。

## 范围与运行位置

使用官方 `deepseek-ai/deepseek-harness`，锁定 npm 包 `@deepseek-ai/dsh@0.2.1-rc.2` 及其依赖。模型为已实测的 `deepseek-flash`，采用 high 推理强度。开发工具配置与游戏自身的 DeepSeek 接入相互独立，不改变游戏业务功能。

本机启动入口默认工作目录为 `/workspace`，自动化任务在 `/workspace/langrensha-agent` 执行。配置使用 `danger-full-access` 与 `approval.policy: never`，用于用户要求的无人值守云端开发；这是完整文件访问权限，不能作为文件隔离承诺。DSH 以单个会话串行处理 Issue；不创建子代理、团队或其他并行开发会话。每个 Issue 使用独立 worktree、分支和 PR，通过 `cwd` 隔离工具工作区。关闭会话日志贡献和 OTel 上传；模型请求仍包含任务所需源码和工具结果。

云环境内的进程随环境生命周期停止；跨休眠执行必须依赖宿主提供的定时器，当前没有可用的云端定时器。2026-10-25 监督者已手动停用 GitHub Actions 工作流 `DeepSeek 每小时验收与串行开发`（ID 395627924，状态 `disabled_manually`），本项 GitHub 调度已撤销，不得重新启用。它原本只做状态验收，且不表示聊天助手每小时重新上线或已完成人工业务验收。

Codex 原生定时任务：当前会话没有 Automations 创建接口，独立 CLI 调用返回 401；本环境未创建或运行 Codex 原生定时任务。GitHub 调度已按上文撤销；仅写 `automation.toml` 不构成创建或运行证据。详见“调度现状与限制”。

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
| GitHub Secrets | 调度停用后不再需要维护 Actions Secrets；不要把“已配置密钥”当作 GitHub 调度可用的证据。 |
| Codex 原生定时 | 当前会话无 Automations 创建接口；独立 CLI 调用返回 401；未创建或运行 Codex 原生定时任务。 |
| DSH 本地服务 | Web 服务监听 `127.0.0.1:3080`，在线但空闲不等同于正在开发；headless 只在被赋予一次性任务时运行。 |

官方文档入口：[Automations](https://learn.chatgpt.com/docs/automations?surface=app)。本环境不另写替代定时平台，也不通过代理、重登或读取认证文件绕过限制。

原先为 Actions 准备的 Secrets 表和历史调度说明不再代表当前状态。不得把“仅创建 automation.toml”或“Web 服务在线”报告为定时任务已创建或已运行。

## 本机运行事实（2026-10-25 核实）

- 默认工作区：DSH workspace 存储只记录 `/workspace`，Web 与 headless 进程的工作目录均为 `/workspace`。
- 本地 Web 服务：`127.0.0.1:3080` 正在监听，未认证请求返回 401，说明服务在线且要求认证；它处于空闲状态，在线本身不是开发进度。
- 运行时密钥：启动入口 `启动DeepSeek.py` 在环境变量缺失时读取仓库外 `~/.config/deepseek-harness/credentials.json`（权限 `0600`，字段非空）；本文不记录密钥值。仓库内未发现该凭据文件。
- 当前 headless 进程：只承载本次一次性核查任务，没有业务开发任务；进程结束即停止，不能据此声称“持续开发”。
- 游戏本地服务：`127.0.0.1:8000` 返回 200，只是本地运行；游戏部署与线上验收由监督者进行，不在本项范围。

## 单人串行与审查（2026-10-26 用户高优先级要求）

用户已明确：DSH 只由单个会话工作，不再开 team；2026-10-25 的 leader + 原生 subagent 团队并行授权由本轮指令取代。禁止创建、fork 或恢复子代理、团队及其他并行开发会话，也不得用命令行另起 DSH/Codex 进程代工。其他无冲突规则继续有效。

1. 配置持久化在 `.github/deepseek-harness/无人值守.patch.yml`。Cordis 的 config 覆盖是整段替换，被禁用的 `tool-subagent` / `tool-subagent-fork` 仍保留完整 `provider`、`toolName`、`maxDepth` 声明，避免启动失败。两个入口及 `tool-subagent-control`、`tool-subagent-list-agents` 均设 `disabled: true`；`subagent.maxActiveSubagents=1` 只是防御性上限，不是“无队员”的实现方式。只改运行时临时覆盖或只写文档不构成持久化交付。
2. 只由当前 DSH 会话创建并维护一个总 goal，串行覆盖当前任务队列；不创建或恢复子级，不使用 `list_agents` / `send_message` 组建团队。
3. 每个 Issue 一个独立 worktree、一个分支和一个 PR，PR 只交付自己的 Issue；同一时刻只处理一个 Issue，完成当前 Issue 后才领取下一个，不混单、不夹带其他 Issue。
4. 开展前先读真实 Issue 正文/讨论、正式需求/设计/规范和 AGENTS，再调研实施。来源必须可追溯；原作事实、改编与项目原创分清；书源授权未核实时不得下载、转存或检索整本小说全文，不以未授权材料替代，不把仓库代码许可证当原作品授权。
5. 每个 PR 正文唯一 `Issue: #编号`，写清范围、正式依据和逐项验收证据。完成必要自查后对最终 head 请求一次 `@codex review`；同 head 已有自动审查不重复。只接受官方 `chatgpt-codex-connector[bot]`、当前 head 且 completed、无未解决发现；修订出新 head 必须重审。running、超时或旧 head 结果不算通过。
6. 5 项必需 CI 必须成功：Python 内核检查、容器构建与启动、文档阶段检查、版本图检查、网页交互与完整发行包。合并前核对主线已包含最新 `main`，PR 过期时同步、解决冲突并重验新 head。
7. 满足审查与 Issue 条件后，用户已授权 DSH 直接合并相应 PR、核对主线检查并关闭完成 Issue；监督者按大版本做最终验收与抽查，不需要用户逐个 PR 批准。不发布 tag/Release 或环境，不修改 GitHub 硬规则，不获取或输出凭据，不编辑 Wiki 或 Project。
8. 旧的串行监督脚本（`.github/scripts/DeepSeek无人值守.py`）与工作流 395627924 作为历史机制保留，不再运行、不重新启用。旧团队并行规则与 `临时/DSH团队/团队状态.md` 等团队运行记录自 2026-10-26 起失效，仅作历史证据保留，不再新增团队记录；不另写团队调度平台或新门禁。

## 报告与停止

单人运行证据由当前会话维护：`临时/DSH单人模式/DSH状态.json` 记录真实 pid、session、goal、当前 Issue、阶段、PR、head 与北京时间，并明确 `single_agent: true`、`team: []`。该文件只作脱敏运行记录，不上传为公开附件。当前 GitHub Actions 调度已停用，不再生成 Actions Summary 或 artifact。模型输出不是独立验证的事实，维护者与监督者仍须核查测试证据、研究来源与 Issue 验收内容；状态检查不冒充线上验收。

暂停任务：保存当前 Issue 的 worktree、分支与未完成证据，保留活动 Issue 供恢复，不派生代理。历史串行监督脚本的 `deepseek-ready`/`deepseek-active` 自动领取与“已有 PR 阻挡下一任务”行为不再适用。完全停止 GitHub 调度：保持工作流 395627924 为 `disabled_manually`，不重新启用。本机 UI 可向启动进程发送 SIGTERM。凭据到期、预算不足、网络失败、Codex 未启用或审查未完成均如实显示阻塞，不能跳过审查。

部署时的真实冒烟验证：Harness 使用 `deepseek-flash` 调用工具，读取 `/workspace/langrensha-agent/AGENTS.md` 第一行并确认工作目录 `/workspace`，退出码 0。该验证只证明 Harness 和工具链可运行，不代表后续业务 Issue 已验收。
