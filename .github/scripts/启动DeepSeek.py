"""本机入口：默认 /workspace，从仓库外凭据文件读取 API key。"""

import json
import os
import sys
from pathlib import Path

from 配置提交身份 import configure_identity

root = Path(__file__).resolve().parents[2]
# 在读取模型凭据之前配置身份；启动失败不会调用模型。
os.environ.update(configure_identity(root))
config = Path.home() / ".config/deepseek-harness/credentials.json"
if not os.environ.get("DEEPSEEK_API_KEY"):
    os.environ["DEEPSEEK_API_KEY"] = json.loads(config.read_text())["DEEPSEEK_API_KEY"]
os.environ.setdefault("DSH_HOME", str(Path.home() / ".local/state/deepseek-harness"))
os.environ.setdefault("DSH_PERMISSION_MODE", "danger-full-access")
os.environ.setdefault("DSH_TELEMETRY_MODE", "DISABLED")
binary = Path(
    os.environ.get("DSH_BIN", str(root / ".github/deepseek-harness/node_modules/.bin/dsh"))
)
patch = root / ".github/deepseek-harness/无人值守.patch.yml"
args = sys.argv[1:] or ["--profile", "web", "--no-open"]
os.chdir("/workspace")
os.execv(str(binary), [str(binary), "--patch", str(patch), *args])
