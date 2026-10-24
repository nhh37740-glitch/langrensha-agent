# HTTPS 部署与备份恢复

本说明对应 #17 / v0.4.0，在已有完整游戏基础上提供生产入口和运维工具；#14 的目标服务器连接尚未取得，本文不表示已在用户服务器上线。

## 服务器准备

服务器需要 Docker Engine、Compose v2.24+，可访问镜像仓库与 api.deepseek.com。域名 A/AAAA 应指向该服务器，允许入站 80/443。先检出已审查的发布 tag，复制 `.env.example` 为 `.env`，权限设为 0600。填入：

- `DEEPSEEK_API_KEY`：私密 API 密钥，始终留在服务器。
- `LANGRENSHA_ACCESS_TOKEN`：至少 32 字符的随机入镇口令。
- `SITE_ADDRESS`：域名或 `https://域名`，不带路径或自定义端口。
- `COOKIE_SECURE=true`。
- `LANGRENSHA_IMAGE=langrensha-agent:v0.4.0`：本机将构建这个镜像标签。

可用 `python -c 'import secrets; print(secrets.token_urlsafe(32))'` 在自己的终端生成口令，再写入私密配置；不要把结果提交到仓库或 Issue。

默认专用网段为 `172.30.91.0/24`，Caddy 为 `.2`，应用为 `.3`。如果与服务器已有网络冲突，**同时**修改 `MIST_PROXY_SUBNET`、`MIST_PROXY_ADDRESS`、`MIST_APPLICATION_ADDRESS`。预检会拒绝不匹配、冲突、网关地址和非私网地址；不自动修改宿主网络。

## 构建、检查和启动

在仓库目录执行：

```bash
部署/运行.sh build
部署/运行.sh check
部署/运行.sh start
部署/运行.sh status
部署/运行.sh audit
```

脚本固定使用私密配置文件，可用 `--env-file /绝对路径/配置.env` 选择另一份配置。`start` 先预检，再仅启动已构建镜像；不会悄悄把未构建源码当成新版本发布。

预检、验证和恢复使用按需启动的 `ops` 容器，避免与运行中应用的固定地址冲突；在线备份在当前应用容器内读取实际已选数据库。

生产 Compose 只有 Caddy 发布 80/443，应用无宿主机端口。Caddy 只接收站点地址，不接收游戏密钥和口令；应用仅信任 Caddy 的固定私网地址传入的 HTTPS 信息。Caddy 证书及 SQLite 都保存在持久卷。停止容器不会删除它们；不要在生产执行 `down --volumes`。

Caddy 自动申请受信证书。容器就绪仅证明进程健康；上线仍须访问 `https://域名/api/health` 核对版本，并在真实入口完成对局、刷新恢复和私密信息隔离验收。首次证书申请失败时查看 `部署/运行.sh logs`，核对 DNS、入站端口与出口策略。

`audit` 只输出决策次数、模型不可用次数、连续失败次数和已接受工具的分类统计，不输出操作者、参数、对白或会话。模型临时不可用会按既定规则弃权；健康接口正常不等于模型从未出现过临时失败。

已有根目录基础 Compose 的数据卷与新生产项目卷名可能不同；先从旧项目取得一致性备份，再导入新卷并核对原会话，保留旧卷用于回退。

## 在线备份

```bash
部署/运行.sh backup before-upgrade.sqlite3
部署/运行.sh verify before-upgrade.sqlite3
```

备份写到应用持久卷 `/data/backups/`，使用 SQLite backup API 获取一致快照，涵盖身份/事件、幂等回执、主持审计和会话摘要。权限 0600，结果只包含数量及 SHA-256，不显示私密内容。已存在的同名文件会拒绝覆盖；不指定名称时使用 UTC 时间。

将备份另存到服务器的受控备份位置，避免主机或整个 Docker 数据目录丢失。备份是私密对局资料，不上传到公开仓库、Actions 附件或聊天。只有与该快照对应、仍保留 cookie 的浏览器能继续原会话，备份不保存浏览器明文 cookie。

## 恢复、激活和回退

```bash
部署/运行.sh restore before-upgrade.sqlite3
```

恢复生成 `/data/restored/before-upgrade.sqlite3`，校验规则版本和完整性，拒绝覆盖已有目标或残留 WAL/SHM/journal。**原数据库保持原样，恢复命令不自动切换当前对局。**

确认要使用快照后，在原私密配置加入 `MIST_DATABASE=/data/restored/before-upgrade.sqlite3`，再运行 `部署/运行.sh start`。Compose 会重新创建应用并使用恢复库；验证旧浏览器会话及历史。需要回退时将 `MIST_DATABASE` 改回原路径（默认 `/data/对局.sqlite3`）再启动。切换前保留当前库的独立备份，避免丢失快照之后的行动。

CLI 也可独立操作文件：

```bash
langrensha-ops check-config --env-file .env
langrensha-ops backup --database 对局.sqlite3 --output 备份.sqlite3
langrensha-ops verify --database 备份.sqlite3
langrensha-ops restore --backup 备份.sqlite3 --database 全新恢复.sqlite3
```

只恢复本程序已知 schema 和 mist-v1 规则，未知版本先明确迁移方案。不要在线覆盖进程正在打开的数据库文件。

## 本机 HTTPS 验收

`python 部署/验收.py --image 已构建镜像` 创建随机 Compose 项目，只映射回环地址，使用 Caddy 的 localhost 测试 CA；Python 显式信任该 CA 验证 TLS，从不关闭证书验证。检查 HTTPS 同源写入、Secure/HttpOnly/SameSite Cookie、私密隔离、在线备份、恢复两个会话及请求去重。结束只清理自己创建的测试项目和卷。

默认使用无模型调用的测试配置。显式加 `--real-env .env` 才读取该私密文件并运行两个真实 AI 窗口；加 `--full-game` 则最多 350 窗口，真人由弃权替身代替，直到胜负，产生 API 费用。结果保存在 `临时/部署验收/`；真实模式留存的数据库和配置均为私密资料。CI 仅运行离线模式，且只上传 `结果.json`。

受管理代理的云环境，运维入口可加 `--ca-bundle /etc/ssl/certs/ca-certificates.crt`，构建和运行都使用只读的会话信任根。直接构建时传 `--secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt`；验收可传 `--ca-bundle /etc/ssl/certs/ca-certificates.crt`，只读挂载运行所需的合并信任根。保留平台代理，不把会话 CA 复制到镜像，不用关闭 TLS 校验修复联网问题。
