# 雾钟镇：狼人杀智能体

一名真人与十一名 DeepSeek AI，在 Phaser 呈现的钟楼广场完成十二人预女猎白文字对局。Python 后端裁定全部技能、警长竞选、平票、死亡触发及胜负；LangGraph 限制原生工具行动循环。真人可以指定或随机取得身份。

完整版本 v0.3.0：世界场景、独立人物动作、可见技能动画、私密频道、来源可追溯的历史检索、人物陈述整理与可编辑发言建议。身份与人格分离，先过滤权限再检索，密钥始终留在服务器。首个剧本为雾钟镇；增加第二个世界后再验收跨世界视觉切换。

## 运行

需要 Python 3.12+ 与 Node.js 24。在仓库目录：

```bash
python -m venv .venv
.venv/bin/python -m pip install -c requirements-dev.lock -e '.[dev,ai,web]'
npm ci --prefix 前端
npm run build --prefix 前端
cp .env.example .env
chmod 600 .env
# 编辑 .env 填入 DEEPSEEK_API_KEY，勿提交密钥。
.venv/bin/langrensha-web
```

打开 http://127.0.0.1:8000 。选择身份、从容决定，浏览器逐窗口推进其他旅人的行动，可随时暂停；没有游戏倒计时。刷新恢复同一局。札记回答只引用自己有权看到的背景与证词，建议由真人编辑后自行发言。

[完整运行、验收、wheel 与容器部署说明](文档/开发/完整可玩版运行与部署.md)包含可复现命令。完整发行包从 GitHub Actions“前端与发行包检查”下载，已包含网页及 Phaser，无需外部 CDN。CI 使用离线替身；真实 DeepSeek 验收另记。当前没有用户服务器连接资料，不能把开发环境验收称作已在线上部署。

## 正式依据

- [项目状态](项目说明.md) / [需求基线](文档/需求/需求分析.md)
- [完整版本实施规格与规则裁定](文档/详细设计/首个可玩版本/完整可玩版实施规格.md)
- [验收记录](文档/验收/完整可玩版验收.md) / [v0.3.0 版本图](文档/版本/v0.3.0/版本说明.md)
- [开发流程](文档/规范/开发流程与协作规范.md) / [中文看板](https://github.com/users/nhh37740-glitch/projects/2)
- 历史演练：[v0.1.0 内核](文档/版本/v0.1.0/版本说明.md)、[v0.2.0 DeepSeek](文档/版本/v0.2.0/版本说明.md)

业务代码在 Codex Cloud 开发，经 Issue、分支、PR、GitHub Actions 和 GitHub agent 审查合入，再打功能 tag。每版用仓库内 Archify 3.2.0 维护与已提交源码相符的图；其 MIT 许可证及第三方声明保留。Wolfcha 仅为第三方研究参考，不随本项目发布。
