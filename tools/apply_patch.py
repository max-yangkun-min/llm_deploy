#!/usr/bin/env python3
"""兼容入口:真正实现在 `deploy-portal/tools/apply_patch.py`。

这两个目录里原本各有一份**字节完全相同**的副本,改一处必须记得改另一处;
两边一旦跑偏,就会出现「换个路径调用就换了个行为」这种最难查的问题。现在只保留
一份实现,这个文件只做转发,两个路径都还能用。

用法和参数完全同 `deploy-portal/tools/apply_patch.py`:
    python tools/apply_patch.py <patch-file> [--backend auto|codex|builtin]
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "deploy-portal" / "tools" / "apply_patch.py"

if __name__ == "__main__":
    if not TARGET.is_file():
        raise SystemExit("找不到实现文件: %s" % TARGET)
    runpy.run_path(str(TARGET), run_name="__main__")
