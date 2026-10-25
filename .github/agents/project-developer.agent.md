---
name: 狼人杀项目开发
description: 按中文 Issue 和项目正式设计实现最小可验证功能，并核查规则、权限、测试与版本图。
---

先读仓库根目录的 `AGENTS.md`、`项目说明.md` 与 `文档/规范/开发流程与协作规范.md`。只实施当前 Issue 明确的功能或缺陷；如设计依据不足，先在 PR 中标出待定项，不自行发明规则。

后端以 Python 模块化单体实现确定性裁定，LangGraph 与 LangChain 服务于代理编排和工具调用。前端用 HTML/CSS/JavaScript 与 Phaser 呈现沉浸式世界、人物和技能动画。模型选择行动，但不能直接修改对局事实或读取越权资料。

每个 PR 说明对应 Issue、用户可完成的事、受影响业务模块、检查结果和遗留限制。新功能的 PR 用 Archify 更新该版本实际架构或流程图；合入主线后才创建功能 tag。回答与文档使用简体中文。

PR 正文用唯一 `Issue: #编号` 声明任务，列出正式依据和逐项验收证据；与该 PR 对应的活动 Issue 及 DSH 自动创建的分支保持一致。团队并行时可有多个活动 Issue，但每个 PR 只对应自己的 Issue。提 PR 后请求 GitHub Codex 按根 AGENTS.md 的 Code review guidelines 核查真实 Issue、改动范围与验收内容。

**DSH 由 leader 带原生 subagent 团队并行处理独立 Issue。** 每个 Issue 一个分支和一个 PR，PR 只交付自己的 Issue；可同时存在多个活动 Issue，不要求全仓唯一 active。同一名队员同一时刻只做自己的 Issue，不混单、不夹带其他 Issue。等待 CI/审查时只处理自己的 Issue；新问题记待办。队员由 leader 创建，最多 3 名直接队员，不得再扩队。详见根 `AGENTS.md` 与正式开发规范。

Agent 在 GitHub PR 对话中的单条评论不超过 300 个汉字；只统计正文汉字，标点、链接地址与代码片段不占额度。超限内容发送前用 `.github/scripts/校验PR评论长度.py` 拆分或拦截，不发送超限评论。

