# RAG 语义检索说明

对应 Issue #43。检索仍先生成受限玩家视图，再切块、向量化并返回原文出处；权限过滤发生在索引之前，不把受限资料交给模型。

## 模型与固定版本

选用 `Qdrant/bge-small-zh-v1.5` 的 ONNX 版本，底座为 `BAAI/bge-small-zh-v1.5`（4 层、隐藏维度 512、中文语义模型）。许可证为 MIT。

| 项目 | 固定值 |
| --- | --- |
| ONNX 模型仓库 | `Qdrant/bge-small-zh-v1.5` |
| 模型仓库提交 | `46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59` |
| 底座模型 | `BAAI/bge-small-zh-v1.5` |
| 底座提交 | `7999e1d3359715c523056ef9478215996d62a620` |
| 模型文件 | `model_optimized.onnx`，94,781,076 字节，SHA-256 `1294ea4b6331115a353d81f96b85e8c8d7fdcc284453d5b2fab5b016230aad38` |
| 分词器 | `tokenizer.json`，439,125 字节，SHA-256 `48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26` |
| 模型页 | https://huggingface.co/Qdrant/bge-small-zh-v1.5 |

模型权重不进入 Git。首次使用时按固定提交和 HTTPS 地址下载到本机缓存，逐个文件校验 SHA-256；校验失败会删除损坏文件并明确报错，下次查询在冷却后重试，不能用损坏权重假装向量化。

## 选型依据

在 CPU 上对同一底座的两种 ONNX 转换做了实测（本机 5 vCPU）：

| 候选 | 文件大小 | 60 条短文本耗时 | 峰值内存 | 许可证 |
| --- | --- | --- | --- | --- |
| `Qdrant/bge-small-zh-v1.5`（fp32，采用） | 94.8 MB | 152～262 ms | 231～238 MB | 仓库标注 MIT |
| `Xenova/bge-small-zh-v1.5`（int8） | 23.9 MB | 84 ms | 205 MB | 底座 MIT，转换仓库未单列许可证 |

两者在中文同义召回样例上结果一致。选择 fp32 版本优先保证精度与许可证标注清晰；94.8 MB 权重、238 MB 峰值内存仍属轻量 CPU 方案，不引入 GPU、外部向量服务或自建平台。若后续部署资源更紧，可在单独 Issue 中评估量化版本。

## 安装与运行

```bash
.venv/bin/python -m pip install -c requirements-dev.lock -e '.[dev,ai,web,rag]'
```

`rag` 额外依赖固定为 `numpy==2.5.4`、`onnxruntime==1.31.0`、`tokenizers==0.23.3`。不安装时检索会回退词项检索并在结果中返回 `warning`，不会伪造语义结果。

运行配置：

- `LANGRENSHA_MODEL_DIR`：指定已预置模型文件的目录（目录内须有 `model.onnx` 与 `tokenizer.json`）；默认 `~/.cache/langrensha/models/bge-small-zh-v1.5-46fbe35fd437`。
- `LANGRENSHA_RAG_OFFLINE=1`：禁止联网下载；缓存缺失或损坏时明确报错并回退词项检索。
- `LANGRENSHA_RAG_THREADS`：可选，ONNX Runtime CPU 线程数，默认交给运行库按机器决定。

Docker 部署已安装 `rag` 依赖，并把 `town-models` 命名卷挂到 `/home/town/.cache/langrensha`，模型只需下载一次。首次语义检索需要能访问模型固定地址；受限网络可提前把两个文件放入该卷，或设置 `LANGRENSHA_MODEL_DIR` 指向预置目录。

## 分块、权限与索引

- 世界书条目、身份指导、对局事件分别作为文档来源；按 `。！？；!?;` 和换行切块，单块最多 300 字符，超长单句按长度硬切，拼接后保持原文顺序。
- 每块保留 `source`、原文、`category`、世界（雾钟镇）、对局 id、说话人座位、回合、事件时间、可见座位与分块序号。
- 检索前先由 `player_view` 生成受限视图；`build_chunks` 只接收该视图里的文档，因此狼人私聊、他人星兆和其他对局不会进入索引。
- `SemanticIndex.build(...)` 每次按当前视图重建；`rebuild_index()` 清空向量缓存后，下一次查询重新计算。向量缓存以文本为键、上限 4096 条，不跨权限复用元数据。
- 余弦相似度低于 0.40 的分块不作为命中，避免无意义查询返回资料；同一来源的多个分块只保留得分最高的一块。该阈值由本 Issue 的实现实测确定，不是平台默认值。
- 查询与文档都不加 BGE 官方查询指令前缀：本机中文同义样例加前缀后得分反而下降，故按实测选择无前缀。

## 模型不可用

依赖缺失、下载失败、TLS/网络错误、权重校验失败或推理异常都会抛出 `EmbeddingUnavailable`，由检索层转换为 `method: "lexical_fallback"` 与 `warning`，继续使用原有 BM25 风格词项检索。返回给玩家的 warning 保持简短，详细原因写入服务器日志；不能把回退结果标成语义检索。启用札记模型整理时，`assistant.assist` 会保留 `retrieval_method` 与 `warning`，不会在二次整理时丢失降级提示。没有关闭 TLS 校验或绕过代理的逻辑。

## CPU 实测

本机（5 vCPU，AMD EPYC 共享环境）用 60 条互不重复的短文本与一条中文查询，在全新进程加载模型后计时；多次实测耗时 0.15～0.26 秒，峰值内存 231～238 MB：

```text
ms≈152–262  peak_mb≈231–238  count=60
```

单条短查询约 2 ms；缓存已就绪时模型加载和权重校验约 0.3 秒，首次还需下载并校验 94.8 MB 权重。复现命令：

```bash
.venv/bin/python -m pytest tests/test_semantic_retrieval.py -q -s
```

测试会真实加载固定版本模型，验证：

- 与目标文本没有共同汉字的同义问法能召回铁匠证词；
- 分块保留来源、世界、对局、说话人、回合、事件时间和可见座位；
- 狼人身份指导不会出现在镇民视图，跨局私聊不会泄露；
- 模型缺失或权重损坏时返回 `lexical_fallback` 与警告，损坏权重不会被使用；
- 全新进程的 CPU 耗时和峰值内存不超过宽松上限（20 秒、1.5 GB）。

## 相关文件

- `src/langrensha/semantic.py`：固定版本下载、校验、ONNX 推理、向量缓存与失败报告。
- `src/langrensha/retrieval.py`：分块、权限前置的临时索引、语义/词项检索与出处。
- `tests/test_semantic_retrieval.py`：真实模型、同义召回、权限隔离、CPU 预算和失败回退测试。
