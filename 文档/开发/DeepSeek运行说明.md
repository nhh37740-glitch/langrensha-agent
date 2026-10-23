# DeepSeek 接入与验证

对应 [Issue #10](https://github.com/nhh37740-glitch/langrensha-agent/issues/10)，属于 #3 的当前内核接入部分。[实施范围](../详细设计/首个可玩版本/DeepSeek决策实施范围.md)说明已实现能力及未实现角色。

## 初始化

Python 3.12 起，在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -c requirements-dev.lock -e '.[dev,ai]'
```

基础内核仍不依赖模型框架；`ai` 为选装依赖。CI 安装 `dev,ai`，用模型替身验证控制流，不需要或调用真实 API 密钥。

## 私密配置

把 `.env.example` 复制为 `.env`，在私密配置中填写 `DEEPSEEK_API_KEY`，默认模型为 `deepseek-flash`，也可指定接口实际支持的 `deepseek-v4-pro`。`.env` 已忽略，不得添加到 Git、PR 或 Actions 日志。部署时应使用服务器的私密环境变量，而非把本次云端配置当作长期密钥管理。

本次用户提供的密钥已配置在当前云端工作区的 `.env`，文件权限为 0600；仓库示例保留空值。程序使用官方 `https://api.deepseek.com`，不会从配置中接受任意模型服务地址。优先使用已有环境变量，CLI 只按指定文件补充未设置的变量。

## 真实验证

```bash
.venv/bin/python -m langrensha.ai_demo --env-file .env --max-rounds 3
```

这会创建并清理私密临时数据库，选一名 AI 狼人执行单个行动窗口，向真实 DeepSeek 发送该玩家已过滤的视图与工具。最多三次模型请求；一次回复中的工具数量也有上限。控制台只报告模型名、请求轮数、工具调用计数、结束原因和权限检查结果，不输出私聊、选票、模型私有推理或密钥。

结束原因为 `acted` 表示模型确实通过合法工具完成行动；仅文字描述行动不算成功。`thinking_rounds_exhausted` 表示后台按同阶段真人规则弃权；`model_unavailable` 表示连接或供应商失败并弃权。二者以不同原因进入主持审计。原阶段已经结束则返回 `window_closed`，不会把旧选择应用到新窗口。请求超时用于识别网络故障，不给玩法增加计时。

每次行动均重新装配上下文。模型连接可以复用，消息、身份工具与阶段不会跨玩家继承；人格资料不能增加权限。运行时关闭 LangSmith 自动追踪，不保存模型私有推理；调用参数和规则结果留在仅主持可读的本机审计表。

## 受信应用层

```python
from langrensha.ai import DecisionConfig, DecisionRunner, DeepSeekConfig, Persona

# player 是应用层认证后由 GameService 绑定的 PlayerSession。
runner = DecisionRunner(DeepSeekConfig.from_env().client(), DecisionConfig(max_rounds=3))
result = runner.run(player, Persona('守桥人', '细心观察，谨慎表达。'))
```

应用层决定何时轮到 AI，并传入它自己的已绑定会话。不要把主持服务或自由选择座位的接口暴露给模型。后台自动弃权与审计方法也不进入模型的工具表。

目前仍是内核演练，尚未实现特殊角色结算、完整对局、较早历史 RAG、网页或线上部署。
