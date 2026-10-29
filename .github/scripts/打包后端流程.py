"""只打包离线阅读所需的页面、使用说明和许可；检查入口链接与离线资源。"""

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "文档/架构/后端运行流程"
SKILL = ROOT / ".agents/skills/archify"


class Links(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        # 查看源码等超链接允许联网，展示页面本身不依赖 CDN。
        resource = attrs.get("src") if tag in {"script", "img", "iframe"} else None
        if tag == "link" and attrs.get("rel") == "stylesheet":
            resource = attrs.get("href")
        if resource and urlsplit(resource).scheme in {"http", "https"}:
            raise ValueError(f"页面依赖在线资源：{resource}")
        if tag == "a" and (href := attrs.get("href")):
            parsed = urlsplit(href)
            if not parsed.scheme and parsed.path:
                target = PAGES / unquote(parsed.path)
                if target.parent != PAGES or not target.is_file():
                    raise ValueError(f"离线入口链接无效：{href}")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("用法：打包后端流程.py <输出.zip>")
    pages = sorted(PAGES.glob("*.html"))
    if len(pages) != 7 or not (PAGES / "打开我.html").is_file():
        raise ValueError("需要一个入口和六张 HTML 流程图")
    for page in pages:
        Links().feed(page.read_text(encoding="utf-8"))
    entries = [(path, path.name) for path in [*pages, PAGES / "使用说明.md"]]
    entries.extend(
        (SKILL / source, "许可/" + target)
        for source, target in (
            ("LICENSE", "Archify许可证.txt"),
            ("THIRD_PARTY_NOTICES.md", "第三方声明.md"),
            ("assets/JetBrainsMono-OFL.txt", "字体许可证.txt"),
        )
    )
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path, name in entries:
            archive.write(path, "后端运行流程/" + name)
    print(f"已打包 {len(entries)} 个文件：{output}")


if __name__ == "__main__":
    main()
