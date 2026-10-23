"""将仓库发布的图与完整校验过的再生成产物绑定，允许跨 runner 的绝对路径变化。"""

import hashlib
import json
import sys
from pathlib import Path, PureWindowsPath
from uuid import UUID


def identity(data):
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def verify(source, published, generated):
    source_bytes = source.read_bytes()
    published_bytes = published.read_bytes()
    if published_bytes != generated.read_bytes():
        raise ValueError("仓库 HTML 与经过浏览器检查的再生成 HTML 不一致，请重新交付版本图")
    diagram_type = json.loads(source_bytes)["diagram_type"]
    for artifact in (published, generated):
        receipt = json.loads(artifact.with_suffix(".delivery.json").read_text(encoding="utf-8"))
        expected = {
            "schemaVersion": 1,
            "status": "current",
            "command": "deliver",
            "type": diagram_type,
        }
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise ValueError(f"{artifact.name} 的交付凭据类型或状态无效")
        UUID(receipt["receiptId"])
        # 绝对工作目录因开发机和 runner 而异；文件名和内容身份必须一致。
        if (
            PureWindowsPath(receipt["input"]).name != source.name
            or PureWindowsPath(receipt["output"]).name != artifact.name
        ):
            raise ValueError(f"{artifact.name} 的交付凭据指向其他文件")
        if receipt["specification"] != identity(source_bytes):
            raise ValueError(f"{artifact.name} 的图源与交付凭据不一致")
        if receipt["artifact"] != identity(published_bytes):
            raise ValueError(f"{artifact.name} 的 HTML 与交付凭据不一致")


def main():
    if len(sys.argv) != 4:
        raise SystemExit("用法：校验版本图.py <图源.json> <仓库.html> <再生成.html>")
    try:
        verify(*(Path(value) for value in sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(str(error)) from None
    print("图源、仓库 HTML、再生成 HTML 与两份交付凭据一致")


if __name__ == "__main__":
    main()
