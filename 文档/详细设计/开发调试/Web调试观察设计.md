# Web 调试观察设计（Issue #64）

制定日期：2026-10-25。对应 Issue：#64。实施分支：`deepseek/issue-64`，基线 `0732de1`（#63 合并后的最新 main）。状态：分支内实现，待 PR、Codex 审查与既有 CI；不发布、不打 tag/Release、不部署。

## 1. 目标与边界

开发阶段 Web 默认开启调试观察，让监督者/开发者能在网页上按轮次、阶段、玩家查看：

- 每位 AI 玩家本回合实际返回的**显式说明**（`AIMessage.content`），不是隐藏推理，也不补写；
- 该回合实际发生的工具调用与结果摘要；
- 狼队真实内部对话（真实 `wolf_chat` 事件，含人类狼与 AI 狼）；
- 无法取得说明时的准确缺失标记；
- 清晰的调试标识与开关；关闭后 Web 不再取得/展示审计数据，恢复正常玩家信息可见范围。

不在本单范围：把调试数据发给 AI 玩家、改变规则/工具权限、推断或伪造模型内部思维、生产环境审计导出、模型评测平台。

## 2. 数据流

```text
模型 AIMessage(content, tool_calls)
  -> DecisionRunner 每步记录 {step, content, has_content, tool_calls}
  -> report {round, phase, phase_id, thinking, calls, reason, acted}
  -> ai_decisions（受信主持表，已有）
  -> presentation.debug_timeline(state, decisions)
  -> GET /api/debug（仅当前 web session 的游戏）
  -> 前端 #debug-panel（默认开启，按轮次/阶段/玩家/狼队对话渲染）
```

`DecisionRunner` 只保存模型可见内容：字符串内容或文本块；provider 异常、请求头、环境值、额外元数据、隐藏推理不落库。内容为空时 `has_content=false`，不补写。模型不可用或无模型回合时 `thinking=[]`，保留既有 `reason`。

系统提示词要求模型每次调用工具前给出一句不超过 80 字的可见判断依据，并明确“只进入 Web 调试观察，不是公开发言，不要复述不应公开的秘密”。这提高显式说明的可获得性，但不改变工具权限或胜负规则；模型仍可能返回空内容，此时只能如实标记缺失。

## 3. 接口

### 3.1 `GET /api/debug`

需要已入镇 cookie；只读取当前 session 绑定的 `game_id`，不接受任意 `game_id` 参数。响应：

```json
{
  "enabled": true,
  "game_id": "…",
  "rounds": [
    {
      "round": 1,
      "phases": [
        {
          "phase": "night_wolves",
          "phase_id": "…",
          "label": "夜裔密谈",
          "players": [
            {
              "seat": 2,
              "name": "灯匠",
              "role": "夜裔",
              "alive": true,
              "decisions": [
                {
                  "time": "…",
                  "reason": "acted",
                  "acted": true,
                  "thinking": [
                    {"step": 1, "content": "…", "has_content": true, "tool_calls": [{"name": "wolf_chat", "args": {"text": "…"}}]}
                  ],
                  "calls": [{"tool": "wolf_vote", "args": {"target": 5}, "result": {"accepted": true}}],
                  "missing": []
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "wolf_chat": [
    {"round": 1, "phase": "night_wolves", "seat": 2, "name": "灯匠", "text": "…", "time": "…"}
  ],
  "missing": [
    {"seat": 3, "round": 1, "phase": "night_wolves", "reason": "model_unavailable", "label": "模型不可用，未返回显式说明"}
  ]
}
```

- `debug=false` 或无对局：返回相同结构，`rounds`/`wolf_chat`/`missing` 为空，不返回任何审计内容。
- 数据按 round、阶段出现顺序、seat 排序；阶段 label 取当前世界书 `THEMES[...]["chapters"]`，缺失回退 phase 原值。
- 人物名、角色名取当前世界书公开 personas/role_labels；角色在调试面板中标“调试可见”。
- 狼队对话只从 host snapshot 的真实 `wolf_chat` 事件生成，按时间排序；没有就返回空，不生成占位对话。
- `missing` 来自真实 report：`model_unavailable`、`no_content`、`window_closed`/无模型回合；不把工具调用伪装成思考。

### 3.2 `POST /api/debug`

请求严格 `{"enabled": bool}`；仅更新当前 `web_sessions.debug`。关闭后 GET 立即不再返回审计数据；重新开启后恢复。默认新会话 `debug=1`；旧表通过 `PRAGMA table_info` + `ALTER TABLE` 迁移为默认开启。

### 3.3 不进入玩家视图

`/api/state`、`present`、`PlayerSession.view()` 不增加 `thinking`、`calls`、`wolf_chat`、`debug` 或审计表字段。AI 决策循环只持有自己的受限视图，调试端点不参与 AI 请求；因此调试不会向 AI 玩家注入其他玩家秘密。

## 4. 页面

- `#debug-toggle` 在 header，默认 `aria-pressed=true`；显示“调试 开/关”，带状态点。
- `#debug-panel` 仅在有对局时显示；入口页只保留开关，避免空白面板。
- 面板结构：调试标识与说明（仅 Web 可见、不向 AI 注入秘密）→ 按轮次分组的阶段/玩家卡 → 每回合的显式说明、工具调用摘要、缺失标记；侧栏为真实狼队内部对话与缺失汇总。
- 所有 API 文本用 `textContent`/DOM 写入，不使用 `innerHTML`。
- 关闭时立即隐藏、清空并停止轮询；刷新后按服务端 session 状态恢复开关。
- 390px 下纵向布局、无横向溢出；减少动效下仍可开关和阅读。
- 默认每 1.5s 拉取一次；请求在途去重，关闭/离场停止。

## 5. 测试与证据

后端：

- `tests/test_debug_mode.py`：report thinking/round/phase、空内容、模型异常、window_closed、debug_timeline 真实事件/角色/人物/狼队对话/缺失、`/api/debug` 认证、默认开启、关闭隐藏、重开恢复、非法 body、玩家视图与版本不变、旧会话表迁移。
- `tests/test_ai.py` 仅增加断言，既有语义不改；`tests/test_retrieval_web.py` 继续通过。
- 全量 pytest（本地排除 4 项缺 numpy 的语义模型用例；CI 安装完整 rag 依赖）。

前端 Playwright：

- 默认开启可见，`/api/debug` 状态与对局绑定；
- 人类狼真实提交 `wolf_chat` 后，狼队对话出现在面板；
- 关闭后隐藏、清空、停止轮询，`/api/debug` 不再返回审计；刷新后保持关闭；重新开启恢复；
- mock 审计数据验证轮次/阶段/玩家/显式说明/工具摘要/缺失标记渲染；
- 390px 可开关且无横向溢出。

真实模型验证：本地使用真实 DeepSeek `DecisionRunner` 推进一次狼人行动，确认 `AIMessage.content` 被原样保存并在面板显示；若模型返回空内容，面板显示“未返回显式说明”，不补写。CI 使用离线替身，不访问真实密钥；离线 runner 不由 `DecisionRunner` 记录 thinking 时，面板显示 0 条/缺失，不使用假数据。

## 6. 与版本图

Issue #64 的调试观察是开发阶段可观测能力，不是四世界主题本身。正式设计图按项目 Archify 维护，记录 Web 开关/会话、DecisionRunner 审计、`/api/debug`、debug_timeline 与前端面板；图中只画已实现路径，不画计划中或未接入的审计能力。图与版本说明的发布状态另行如实记录；不因本单提前打 tag/Release。
