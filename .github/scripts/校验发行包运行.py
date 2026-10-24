"""从独立工作目录启动已安装的 wheel，验证私密配置定位和自带网页。"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def main():
    executable = Path(sys.argv[1]).resolve()
    runtime = Path("临时/网页发行包/独立运行").resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / ".env").write_text(
        "DEEPSEEK_API_KEY=ci-placeholder-no-provider-call\n"
        "LANGRENSHA_ACCESS_TOKEN=ci-placeholder-access\nCOOKIE_SECURE=false\n",
        encoding="utf-8",
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = dict(os.environ)
    for key in ("DEEPSEEK_API_KEY", "LANGRENSHA_ACCESS_TOKEN", "DEEPSEEK_MODEL"):
        env.pop(key, None)
    log_path = runtime / "启动.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [
                str(executable),
                "-I",
                "-m",
                "langrensha.web",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
            ],
            cwd=runtime,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("已安装程序启动失败，请检查独立运行日志")
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/api/health", timeout=1
                    ) as r:
                        assert r.status == 200
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("已安装程序未在期限内就绪")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                assert "雾钟镇" in response.read().decode()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    print("独立 wheel 在新目录读取 .env，远程监听认证及生产网页通过；未调用模型 API")


if __name__ == "__main__":
    main()
