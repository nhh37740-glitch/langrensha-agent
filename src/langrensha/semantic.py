"""固定版本的中文语义向量模型；权重不入 Git，失败时明确报告而不伪造向量。"""

from __future__ import annotations

import hashlib
import os
import threading
import time
import urllib.request
from pathlib import Path

MODEL_ID = "Qdrant/bge-small-zh-v1.5"
MODEL_REVISION = "46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59"
BASE_MODEL_ID = "BAAI/bge-small-zh-v1.5"
BASE_MODEL_REVISION = "7999e1d3359715c523056ef9478215996d62a620"
MODEL_LICENSE = "MIT"
MODEL_PAGE = f"https://huggingface.co/{MODEL_ID}"
MODEL_URL = f"{MODEL_PAGE}/resolve/{MODEL_REVISION}/model_optimized.onnx"
TOKENIZER_URL = f"{MODEL_PAGE}/resolve/{MODEL_REVISION}/tokenizer.json"
MODEL_SHA256 = "1294ea4b6331115a353d81f96b85e8c8d7fdcc284453d5b2fab5b016230aad38"
TOKENIZER_SHA256 = "48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26"
MODEL_FILENAME = "model.onnx"
TOKENIZER_FILENAME = "tokenizer.json"
EMBEDDING_DIM = 512
MAX_TOKENS = 512
BATCH_SIZE = 32
CACHE_LIMIT = 4096
FAILURE_COOLDOWN = 30.0

_DOWNLOAD_CHUNK = 1024 * 1024


class EmbeddingUnavailable(RuntimeError):
    """真实模型、依赖或权重不可用；调用方必须报告并回退，不得假装已向量化。"""


class _Runtime:
    __slots__ = ("session", "tokenizer")

    def __init__(self, session, tokenizer):
        self.session = session
        self.tokenizer = tokenizer


_RUNTIME: _Runtime | None = None
_RUNTIME_LOCK = threading.Lock()
_FAILED_MESSAGE = ""
_FAILED_UNTIL = 0.0
_CACHE: dict[str, object] = {}
_CACHE_LOCK = threading.Lock()
_INFER_LOCK = threading.Lock()


def model_directory() -> Path:
    """返回固定模型版本的本地目录；可用 LANGRENSHA_MODEL_DIR 指向预置目录。"""
    override = os.environ.get("LANGRENSHA_MODEL_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    short = MODEL_REVISION[:12]
    return Path.home() / ".cache" / "langrensha" / "models" / f"bge-small-zh-v1.5-{short}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_DOWNLOAD_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, destination: Path, expected: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f"{destination.name}.{os.getpid()}.part")
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "langrensha-agent/0.5 (+semantic-retrieval)"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            with temporary.open("wb") as handle:
                for block in iter(lambda: response.read(_DOWNLOAD_CHUNK), b""):
                    handle.write(block)
        actual = _sha256(temporary)
        if actual != expected:
            raise EmbeddingUnavailable(
                f"模型文件校验失败：{destination.name} 期望 {expected}，实际 {actual}"
            )
        os.replace(temporary, destination)
    except EmbeddingUnavailable:
        temporary.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise EmbeddingUnavailable(f"下载语义模型失败：{url}（{exc}）") from exc


def _ensure_file(path: Path, url: str, expected: str) -> None:
    if path.is_file():
        if _sha256(path) == expected:
            return
        path.unlink()
    if os.environ.get("LANGRENSHA_RAG_OFFLINE", "").strip() == "1":
        raise EmbeddingUnavailable(
            f"语义模型文件缺失或损坏：{path}；已设置 LANGRENSHA_RAG_OFFLINE=1，禁止联网下载"
        )
    _download(url, path, expected)


def _load_runtime() -> _Runtime:
    global _RUNTIME, _FAILED_MESSAGE, _FAILED_UNTIL
    now = time.monotonic()
    if _RUNTIME is not None:
        return _RUNTIME
    if now < _FAILED_UNTIL:
        raise EmbeddingUnavailable(_FAILED_MESSAGE)
    with _RUNTIME_LOCK:
        if _RUNTIME is not None:
            return _RUNTIME
        if time.monotonic() < _FAILED_UNTIL:
            raise EmbeddingUnavailable(_FAILED_MESSAGE)
        try:
            try:
                import onnxruntime
                from tokenizers import Tokenizer
            except ImportError as exc:
                raise EmbeddingUnavailable(
                    f"缺少语义检索依赖，请安装 rag 额外依赖（{exc}）"
                ) from exc
            directory = model_directory()
            _ensure_file(directory / MODEL_FILENAME, MODEL_URL, MODEL_SHA256)
            _ensure_file(directory / TOKENIZER_FILENAME, TOKENIZER_URL, TOKENIZER_SHA256)
            options = onnxruntime.SessionOptions()
            threads = os.environ.get("LANGRENSHA_RAG_THREADS", "").strip()
            if threads.isdigit() and int(threads) > 0:
                options.intra_op_num_threads = int(threads)
            session = onnxruntime.InferenceSession(
                str(directory / MODEL_FILENAME),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            tokenizer = Tokenizer.from_file(str(directory / TOKENIZER_FILENAME))
            tokenizer.enable_truncation(max_length=MAX_TOKENS)
            _RUNTIME = _Runtime(session, tokenizer)
            return _RUNTIME
        except EmbeddingUnavailable as exc:
            _FAILED_MESSAGE = str(exc)
            _FAILED_UNTIL = time.monotonic() + FAILURE_COOLDOWN
            raise
        except Exception as exc:
            _FAILED_MESSAGE = f"语义模型加载失败：{exc}"
            _FAILED_UNTIL = time.monotonic() + FAILURE_COOLDOWN
            raise EmbeddingUnavailable(_FAILED_MESSAGE) from exc


def _embed_batch(runtime: _Runtime, texts: list[str]):
    import numpy as np

    encodings = [runtime.tokenizer.encode(text) for text in texts]
    width = max(len(encoding.ids) for encoding in encodings)
    input_ids = np.zeros((len(texts), width), dtype=np.int64)
    attention = np.zeros_like(input_ids)
    for row, encoding in enumerate(encodings):
        length = len(encoding.ids)
        input_ids[row, :length] = encoding.ids
        attention[row, :length] = 1
    token_types = np.zeros_like(input_ids)
    feeds = {
        "input_ids": input_ids,
        "attention_mask": attention,
        "token_type_ids": token_types,
    }
    accepted = {item.name for item in runtime.session.get_inputs()}
    selected = {key: value for key, value in feeds.items() if key in accepted}
    outputs = runtime.session.run(None, selected)
    vectors = np.asarray(outputs[0][:, 0, :], dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[1] != EMBEDDING_DIM:
        raise EmbeddingUnavailable(
            f"模型输出维度 {vectors.shape} 与固定版本 {EMBEDDING_DIM} 不一致"
        )
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _embed_many(texts: list[str]):
    import numpy as np

    runtime = _load_runtime()
    with _CACHE_LOCK:
        missing = list(dict.fromkeys(text for text in texts if text not in _CACHE))
    for start in range(0, len(missing), BATCH_SIZE):
        batch = missing[start : start + BATCH_SIZE]
        try:
            with _INFER_LOCK:
                vectors = _embed_batch(runtime, batch)
        except Exception as exc:
            raise EmbeddingUnavailable(f"语义推理失败：{exc}") from exc
        with _CACHE_LOCK:
            for text, vector in zip(batch, vectors, strict=True):
                _CACHE[text] = vector.copy()
            while len(_CACHE) > CACHE_LIMIT:
                _CACHE.pop(next(iter(_CACHE)))
    with _CACHE_LOCK:
        return np.stack([_CACHE[text] for text in texts])


def embed(texts):
    """返回 L2 归一化的真实模型向量；调用方负责在失败时明确报告。"""
    items = [text for text in texts if isinstance(text, str) and text.strip()]
    if not items:
        import numpy as np

        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
    return _embed_many(items)


def scores(texts, query: str):
    """计算每个文本与查询的余弦相似度；模型不可用时抛出 EmbeddingUnavailable。"""
    items = [text for text in texts if isinstance(text, str) and text.strip()]
    if not items:
        return []
    if not isinstance(query, str) or not query.strip():
        raise ValueError("查询不能为空")
    try:
        vectors = _embed_many(items)
        query_vector = _embed_many([query])[0]
    except EmbeddingUnavailable:
        raise
    except Exception as exc:
        raise EmbeddingUnavailable(f"语义推理失败：{exc}") from exc
    return [float(value) for value in vectors @ query_vector]


def status() -> dict:
    directory = model_directory()
    files = {
        name: (directory / name).is_file()
        for name in (MODEL_FILENAME, TOKENIZER_FILENAME)
    }
    return {
        "model": MODEL_ID,
        "revision": MODEL_REVISION,
        "base_model": BASE_MODEL_ID,
        "base_revision": BASE_MODEL_REVISION,
        "license": MODEL_LICENSE,
        "directory": str(directory),
        "files": files,
        "ready": all(files.values()),
        "loaded": _RUNTIME is not None,
    }


def reset() -> None:
    """清空向量缓存、模型单例与失败冷却；供测试和显式重建索引使用。"""
    global _RUNTIME, _FAILED_MESSAGE, _FAILED_UNTIL
    clear_cache()
    with _RUNTIME_LOCK:
        _RUNTIME = None
        _FAILED_MESSAGE = ""
        _FAILED_UNTIL = 0.0


def clear_cache() -> None:
    """只清空向量缓存，保留已加载模型；下一次查询重建向量索引。"""
    with _CACHE_LOCK:
        _CACHE.clear()
