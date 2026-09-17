#!/usr/bin/env python3
"""按精确内容新增文件(走 apply_patch,绕开 PowerShell 的参数编组)。

存在的理由和 apply_patch.py 一样:本机 apply_patch 是 .bat 包装器,PowerShell
向原生命令传参时会破坏 patch 里的反斜杠加双引号序列。新文件用 apply_patch 建立
还有一个实际好处:改动会进 Codex 的补丁记录,而不是绕开它悄悄写盘。

用法:
    python tools/add_file.py <目标路径> <内容文件>

目标路径必须不存在。已存在的文件请用 deploy-portal/tools/whole_file_replace.py,
它是分块替换并逐字节校验的。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BEGIN = "*** Begin" + " Patch"
END = "*** End" + " Patch"


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    target = Path(argv[1])
    content_path = Path(argv[2])
    if not content_path.is_file():
        raise SystemExit("内容文件不存在: %s" % content_path)
    if target.exists():
        raise SystemExit("目标已存在,请改用 whole_file_replace.py: %s" % target)

    text = content_path.read_text(encoding="utf-8")
    if text.endswith("\n"):
        text = text[:-1]
    body = ["+" + line for line in text.split("\n")]
    patch = "\n".join([BEGIN, "*** Add File: " + target.as_posix()] + body + [END]) + "\n"

    patch_path = Path(".tmp") / ("add_%s.patch" % target.name)
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(patch, encoding="utf-8")

    script = Path(__file__).with_name("apply_patch.py")
    result = subprocess.run([sys.executable, str(script), str(patch_path)])

    # 结尾必须逐字节对上:apply_patch 静默少写一行时,这里要直接失败,
    # 不能留下一个内容不完整的新文件给下一步用。
    if result.returncode == 0:
        actual = target.read_text(encoding="utf-8")
        expected = "\n".join(text.split("\n")) + "\n"
        if actual != expected:
            target.unlink()
            raise SystemExit("新增后内容不一致,已删除 %s(期望 %d 字符,实际 %d 字符)"
                             % (target, len(expected), len(actual)))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))