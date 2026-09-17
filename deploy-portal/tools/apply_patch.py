#!/usr/bin/env python3
"""可靠的 apply_patch 调用器(Windows / PowerShell 环境)。

背景:本机 `apply_patch` 是 .bat 包装器,PowerShell 向原生命令传参时会把
patch 里的反斜杠加双引号序列破坏掉,导致 patch 校验失败或文件被静默写坏。
本脚本改由 Python 的 subprocess 构造 argv,绕开 PowerShell 的参数编组。

用法:
    python deploy-portal/tools/apply_patch.py <patch-file>

patch 文件必须是 UTF-8(建议无 BOM),结尾不要有空行,最后一行必须是
 *** End Patch。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CODEX_EXE_CANDIDATES = [
    Path.home()
    / "AppData/Roaming/npm/node_modules/@openai/codex/node_modules"
    / "@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe",
]


def find_codex():
    for path in CODEX_EXE_CANDIDATES:
        if path.is_file():
            return path
    raise SystemExit("找不到 codex.exe")


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    patch_path = Path(argv[1])
    if not patch_path.is_file():
        raise SystemExit("patch 文件不存在: %s" % patch_path)
    text = patch_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip("\n")
    last = text.split("\n")[-1]
    if last != "*** End Patch":
        raise SystemExit(
            "patch 最后一行必须精确是 *** End Patch,当前是: %r" % last
        )
    result = subprocess.run([str(find_codex()), "--codex-run-as-apply-patch", text])
    return result.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
