# 狼人杀智能体：多剧本社交推理游戏

本项目计划让一名真人与十一名 AI 在文字为主的沉浸式剧本中完成一局社交推理游戏。首个可玩剧本为十二人预女猎白；以后可更换世界背景、人物、身份能力及相应网页美术和动画。

**当前状态：详细设计，尚无本项目业务代码，也未部署。** 本仓库公开保存已确认的需求、架构方向、详细设计草案和开发流程。历史上的 [Wolfcha](https://github.com/oil-oil/wolfcha) 仅作第三方参考，不随本仓库上传其源码。

## 已确定的方向

- Python 模块化单体后端；LangChain 与 LangGraph 支持受控的 AI 工具调用与对局编排，游戏规则由后端裁定。
- HTML/CSS/JavaScript 前端；使用 Phaser 呈现各世界场景、虚拟角色和身份技能的动画。
- 真人与 AI 按真实身份权限查询可见的世界书和历史发言；狼人私聊与夜间投票只对狼人和主持人可见。
- 业务代码由后续 Codex Cloud 任务开发。本地不编写业务代码；GitHub Issues、PR 和 Actions 管理特性、缺陷与构建。

## 阅读入口

- [项目说明](项目说明.md)
- [开发流程与协作规范](文档/规范/开发流程与协作规范.md)
- [需求分析](文档/需求/需求分析.md)
- [架构与设计模式评估](文档/架构/架构与设计模式评估.md)
- [首个可玩版本详细设计](文档/详细设计/首个可玩版本/详细设计.md)
- [Wiki：阅读导航](https://github.com/nhh37740-glitch/langrensha-agent/wiki)
- [项目看板](https://github.com/nhh37740-glitch/langrensha-agent/projects)

## 协作方式

从最小可测试的对局内核起步。每项新功能或缺陷先建中文 Issue，在分支中实施，通过 PR 与 GitHub Actions 检查后合入 `main`。每项新功能合入后为对应主线提交打 Git tag；每个版本用 Archify 绘制与实际实现相符的图。具体规则以[开发流程](文档/规范/开发流程与协作规范.md)为准。

Codex Cloud 用于编写、构建和验证代码；游戏最终运行位置仍需在实施阶段确定，部署后须核对实际入口和线上对局。当前不把云端开发环境当成已上线服务。

仓库内 `.agents/skills/archify/` 固定保存 Archify 3.2.0，供 Codex Cloud 任务使用；其原始 [MIT 许可证](.agents/skills/archify/LICENSE) 与第三方声明随包保留。当前 GitHub Actions 只检查文档；业务代码出现后再由对应 Issue 补上 Python 与前端构建，不把文档检查称为应用编译。
