#!/usr/bin/env python3
"""整文件替换:用 apply_patch 分块完成,结束时逐字节校验。

存在的两个理由:
1. 本机 `apply_patch` 是 .bat 包装器,PowerShell 直接传参会破坏 patch 里的转义
   序列;必须走 `tools/apply_patch.py`。
2. 单个 patch 文本超过 Windows argv 上限(约 32K)会报 WinError 206,所以整文件
   替换要拆成多个 hunk 依次应用。

用法:
    python deploy-portal/tools/whole_file_replace.py <目标文件> <新内容文件>
    python deploy-portal/tools/whole_file_replace.py <目标文件> <新内容文件> --dry-run

为什么结尾要校验:2026-09-17 的临时版本用 `text.split("\n")[:-1]` 取行,新内容
文件结尾没有换行时会静默丢掉最后一行,结果 recommend.js 少了一个 `}`,浏览器
只报 `SyntaxError: Unexpected end of input`,整页停在「加载中…」而全部接口都是
200。现在结尾有没有换行都不影响结果,并且最终内容对不上就直接非零退出。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

#: 单个补丁的字符预算,远低于 Windows 约 32K 的 argv 上限
BUDGET = 20000
#: 标记行拆开拼接,避免本文件自身被扫描成补丁结束标记
BEGIN = "*** Begin" + " Patch"
END = "*** End" + " Patch"


def read_lines(path):
    """取「文件自身的行」;结尾有没有换行都不丢内容。"""
    text = path.read_text(encoding="utf-8")
    if text.endswith("\n"):
        text = text[:-1]
    return text.split("\n")


def apply_patch(patch_text, workdir, step):
    patch_path = workdir / ".tmp" / ("whole_replace_%03d.patch" % step)
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(patch_text, encoding="utf-8")
    script = Path(__file__).with_name("apply_patch.py")
    result = subprocess.run([sys.executable, str(script), str(patch_path)],
                            capture_output=True, text=True, encoding="utf-8")
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        sys.exit("第 %d 块补丁失败:\n%s" % (step, output.strip()))
    return output.strip().splitlines()[-1] if output.strip() else ""


def main(argv):
    args = [item for item in argv[1:] if not item.startswith("--")]
    dry_run = "--dry-run" in argv
    if len(args) != 2:
        print(__doc__)
        return 2
    workdir = Path.cwd()
    target, new_file = Path(args[0]), Path(args[1])
    old = read_lines(target)
    new = read_lines(new_file)

    # 先切好每一段,再落盘;这样 --dry-run 也能如实报告要动几块。
    segments = []
    index = cursor = 0
    while cursor < len(old) or index < len(new):
        take_old = take_new = cost = 0
        while cursor + take_old < len(old) and cost + len(old[cursor + take_old]) + 2 < BUDGET // 2:
            cost += len(old[cursor + take_old]) + 2
            take_old += 1
        while index + take_new < len(new) and cost + len(new[index + take_new]) + 2 < BUDGET:
            cost += len(new[index + take_new]) + 2
            take_new += 1
        if take_old == 0 and take_new == 0:
            take_new = 1
        if index == 0:
            # 第一块:用文件首行做上下文,后面的块用「上一块写入的新内容末行」。
            # 首行本身就是上下文,已经从 old/new 各占掉一行,不能再进 body,
            # 否则每块都会把上下文行复制一遍(实测会把首行 import 写两遍)。
            #
            # 前提是旧首行与新首行一致。不一致时不能再把它当上下文——那样新首行
            # 会被丢掉、旧首行原地留下。这种情况发一个无上下文块的补丁。
            if old and new and old[0] == new[0]:
                segments.append((old[0], old[1:take_old], new[1:take_new]))
                cursor, index = take_old, take_new
            else:
                segments.append((None, old[0:1], new[0:1]))
                cursor, index = 1, 1
        else:
            segments.append((new[index - 1], old[cursor:cursor + take_old],
                             new[index:index + take_new]))
            cursor += take_old
            index += take_new

    for step, (context, body_old, body_new) in enumerate(segments):
        print("第 %d 块: -%d 行 +%d 行" % (step, len(body_old), len(body_new)))

    if dry_run:
        print("--dry-run:没有写入。共 %d 块。" % len(segments))
        return 0

    # 分块写完后才校验,所以先把原始内容留在内存里;对不上就整体回滚,
    # 绝不留一个「改了一半」的文件给下一个步骤。
    backup = target.read_text(encoding="utf-8")
    for step, (context, body_old, body_new) in enumerate(segments):
        # context 为 None 时发一个「没有上下文行」的补丁块。首行被改动时要用它:
        # 首块原本拿 old[0] 当上下文,等于假定新旧首行相同,于是新首行被丢掉、
        # 旧首行留下来。没有可用的公共上下文行时,只能直接 -旧 +新。
        hunk = ["@@"] if context is None else ["@@", " " + context]
        hunk += ["-" + line for line in body_old]
        hunk += ["+" + line for line in body_new]
        patch = "\n".join([BEGIN, "*** Update File: " + target.as_posix()] + hunk + [END]) + "\n"
        print("  %s" % apply_patch(patch, workdir, step))

    now = target.read_text(encoding="utf-8")
    expected = "\n".join(new) + "\n"
    if now != expected:
        # Python 3.8 的 Path.write_text 不接受 newline 参数;用它回滚会抛
        # TypeError,于是「回滚」本身把文件留在改了一半的状态——比不回滚更糟。
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(backup)
        sys.exit("替换后内容与源文件不一致(目标 %d 字符,期望 %d 字符),已回滚原文件。"
                 % (len(now), len(expected)))
    print("完成:内容与源文件逐字节一致(%d 行)。" % len(new))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
