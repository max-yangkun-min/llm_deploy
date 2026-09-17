#!/usr/bin/env python3
"""可靠的 apply_patch 调用器(跨平台,带内置引擎兜底)。

为什么要有它(本机)
------------------
`apply_patch` 在本机是 .bat 包装器,PowerShell 向原生命令传参时会把 patch 里的
反斜杠加双引号序列破坏掉,导致 patch 校验失败,或者更糟:文件被静默写坏。
本脚本改由 Python 构造 argv,绕开 PowerShell 的参数编组。

为什么不能只依赖 codex.exe
--------------------------
旧实现只认 Windows 上 npm 装出来的那一条 codex.exe 路径。于是 GitHub Actions
(Linux)上 `whole_file_replace.py` 必然失败——2026-09-17 首次推送后第一次 CI
就是这么红的(整文件替换工具 FAIL:找不到 codex.exe)。一个常年红的门禁,下场是
所有人都学会忽略它,那比没有门禁更糟。现在按下面的顺序选后端:

1. `codex`:本机 npm vendor 目录或 PATH 上的 codex,**而且真的跑得起来**就用——
   改动会进 Codex 自己的补丁记录,这是它相对直接写盘的价值;
2. `builtin`:本文件内置的补丁引擎,不依赖任何外部程序。

内置引擎是**严格**实现:上下文行必须逐字对上,不认识的指令直接报错,所有文件都
算完并且都成功才落盘。它不做模糊匹配、不猜位置——宁可失败,也不留一个改了一半
的文件给下一步。

用法:
    python deploy-portal/tools/apply_patch.py <patch-file>
    python deploy-portal/tools/apply_patch.py <patch-file> --backend builtin

环境变量 `LLM_DEPLOY_PATCH_BACKEND` 等价于 `--backend`(CI 用它强制测内置引擎)。

patch 文件必须是 UTF-8(可带 BOM),最后一行必须是 *** End Patch。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

#: 标记行拆开拼接,避免本文件自身被误当成补丁内容
BEGIN = "*** Begin" + " Patch"
END = "*** End" + " Patch"
BACKENDS = ("auto", "codex", "builtin")


class PatchError(Exception):
    """补丁本身的问题。统一在这里抛,由 main 转成非零退出。"""


def codex_candidates():
    """列出可能可用的 codex 可执行文件,越可能可用的越靠前。

    不写死平台:Windows 上是 codex-win32-x64,类 Unix 上是 codex-linux-x64,
    所以这里按名字扫,而不是钉住某一条路径。
    """
    found = []
    npm_root = Path.home() / "AppData/Roaming/npm/node_modules/@openai/codex/node_modules"
    if npm_root.is_dir():
        found += sorted(npm_root.glob("@openai/codex-*/vendor/*/bin/codex.exe"))
    for name in ("codex", "codex.exe", "codex.cmd"):
        which = shutil.which(name)
        if which:
            found.append(Path(which))
    return found


def codex_works(path):
    """这个候选真的能跑吗?只判断「文件存在」是不够的。

    在 WSL 里 PATH 常常挂着 Windows 的 `AppData/Roaming/npm/codex`,那是个需要
    node 的包装脚本,在 Linux 里跑起来是 `exec: node: not found`。2026-09-17 用
    WSL 复现 CI 时就是它把「默认后端」整条链路判成失败——文件存在,不等于这个用法
    可用。跑不起来的候选直接跳过。
    """
    try:
        result = subprocess.run([str(path), "--version"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def find_codex():
    """返回第一个**真的能跑**的 codex;都不行时返回 None。"""
    for path in codex_candidates():
        if path.is_file() and codex_works(path):
            return path
    return None


def pick_backend(requested):
    """返回 (后端名, codex 路径)。显式要 codex 却用不了时直接报错,不悄悄换后端。"""
    if requested == "builtin":
        return "builtin", None
    exe = find_codex()
    if exe is None:
        if requested == "codex":
            raise SystemExit("指定了 --backend codex,但找不到可用的 codex 可执行文件")
        return "builtin", None
    return "codex", exe


# --- 内置引擎 -------------------------------------------------------------------

def read_text(path):
    """读文本并把换行统一成 LF;补丁是文本,行尾风格不该影响匹配。"""
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def split_file(text):
    """切成行,并记住结尾有没有换行。"""
    trailing = text.endswith("\n")
    return (text[:-1] if trailing else text).split("\n"), trailing


def parse_patch(text):
    """解析成操作列表;不认识的指令直接报错,不猜。"""
    lines = text.strip("\n").split("\n")
    if lines[0] != BEGIN:
        raise PatchError("第一行必须是 %r,当前是 %r" % (BEGIN, lines[0]))
    if lines[-1] != END:
        raise PatchError("最后一行必须精确是 %r,当前是 %r" % (END, lines[-1]))

    body, operations, index = lines[1:-1], [], 0
    while index < len(body):
        head = body[index]
        if head.startswith("*** Update File:"):
            path = head.split(":", 1)[1].strip()
            if not path:
                raise PatchError("*** Update File 后面缺少路径")
            index += 1
            hunks = []
            while index < len(body) and not body[index].startswith("*** "):
                if not body[index].startswith("@@"):
                    raise PatchError("%s 的正文必须以 @@ 开头:%r" % (path, body[index][:60]))
                index += 1
                hunk = []
                while index < len(body) and not body[index].startswith(("@@", "*** ")):
                    hunk.append(body[index])
                    index += 1
                hunks.append(hunk)
            operations.append(("update", path, hunks))
        elif head.startswith("*** Add File:"):
            path = head.split(":", 1)[1].strip()
            if not path:
                raise PatchError("*** Add File 后面缺少路径")
            index += 1
            payload = []
            while index < len(body) and not body[index].startswith("*** "):
                payload.append(body[index])
                index += 1
            operations.append(("add", path, payload))
        elif head.startswith("*** Delete File:"):
            path = head.split(":", 1)[1].strip()
            if not path:
                raise PatchError("*** Delete File 后面缺少路径")
            index += 1
            operations.append(("delete", path, []))
        else:
            raise PatchError("不认识的指令:%r(支持 Update / Add / Delete File)" % head[:60])
    return operations


def locate(lines, need, start):
    """从 start 行往后找 need 这段原文;找不到返回 None。"""
    span = len(need)
    for position in range(start, len(lines) - span + 1):
        if lines[position:position + span] == need:
            return position
    return None


def apply_hunks(lines, hunks, path):
    """逐块应用。每一块都从上一块结束的位置往后找,和 codex 的语义一致。"""
    cursor, result = 0, []
    for number, hunk in enumerate(hunks, 1):
        need, take = [], []
        for line in hunk:
            mark = line[:1]
            if mark not in (" ", "-", "+"):
                raise PatchError("%s 第 %d 块:正文行必须以空格/-/+ 开头:%r"
                                 % (path, number, line[:60]))
            if mark in (" ", "-"):
                need.append(line[1:])
            if mark in (" ", "+"):
                take.append(line[1:])
        if not need:
            raise PatchError("%s 第 %d 块:只有 + 行、没有上下文行或 - 行,"
                             "无法确定插入位置(内置引擎不做猜测)" % (path, number))
        found = locate(lines, need, cursor)
        if found is None:
            raise PatchError("%s 第 %d 块:原文对不上——从第 %d 行起找不到 %r"
                             % (path, number, cursor + 1, need[0][:60]))
        result += lines[cursor:found]
        result += take
        cursor = found + len(need)
    result += lines[cursor:]
    return result


def apply_builtin(text, workdir):
    """应用补丁,返回文件操作数。全部算完并校验通过才落盘。"""
    operations = parse_patch(text)
    if not operations:
        raise PatchError("补丁里没有任何文件操作")
    staged = []
    for kind, raw_path, payload in operations:
        path = Path(raw_path)
        if not path.is_absolute():
            path = workdir / path
        if kind == "update":
            if not path.is_file():
                raise PatchError("要更新的文件不存在:%s" % raw_path)
            lines, trailing = split_file(read_text(path))
            content = "\n".join(apply_hunks(lines, payload, raw_path))
            staged.append(("write", path, content + ("\n" if trailing else "")))
        elif kind == "add":
            if path.exists():
                raise PatchError("要新增的文件已存在:%s" % raw_path)
            body = []
            for line in payload:
                if not line.startswith("+"):
                    raise PatchError("新增文件的正文行必须以 + 开头:%r" % line[:60])
                body.append(line[1:])
            staged.append(("write", path, "\n".join(body) + "\n"))
        else:
            if not path.is_file():
                raise PatchError("要删除的文件不存在:%s" % raw_path)
            staged.append(("delete", path, None))
    for action, path, content in staged:
        if action == "delete":
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            # newline="" 是必须的:默认模式下 Python 会把 \n 写成本平台的行尾,
            # 在 Windows 上就会把补丁写进仓库的内容变成 CRLF。
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write(content)
    return len(staged)


# --- 入口 ----------------------------------------------------------------------

def parse_args(argv):
    backend = (os.environ.get("LLM_DEPLOY_PATCH_BACKEND") or "auto").strip() or "auto"
    rest, index = [], 1
    while index < len(argv):
        item = argv[index]
        if item == "--backend":
            index += 1
            if index >= len(argv):
                raise SystemExit("--backend 后面要跟后端名")
            backend = argv[index]
        elif item.startswith("--backend="):
            backend = item.split("=", 1)[1]
        else:
            rest.append(item)
        index += 1
    if backend not in BACKENDS:
        raise SystemExit("未知后端 %r,可选:%s" % (backend, " / ".join(BACKENDS)))
    return backend, rest


def main(argv):
    backend, rest = parse_args(argv)
    if len(rest) != 1:
        print(__doc__)
        return 2
    patch_path = Path(rest[0])
    if not patch_path.is_file():
        raise SystemExit("patch 文件不存在: %s" % patch_path)

    text = patch_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip("\n")
    last = text.split("\n")[-1]
    if last != END:
        raise SystemExit("patch 最后一行必须精确是 *** End Patch,当前是: %r" % last)

    backend, exe = pick_backend(backend)
    if backend == "codex":
        result = subprocess.run([str(exe), "--codex-run-as-apply-patch", text])
        if result.returncode == 0:
            print("codex 应用成功(%s)" % exe.name)
        return result.returncode
    try:
        count = apply_builtin(text, Path.cwd())
    except PatchError as error:
        sys.stderr.write("补丁未应用(内置引擎):%s\n" % error)
        return 1
    print("内置引擎应用成功(%d 个文件操作)" % count)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
