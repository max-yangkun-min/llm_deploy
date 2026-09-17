#!/usr/bin/env python3
"""项目持续集成门禁:把已经跑通的检查串成一条可重复执行的命令。

为什么要有它
------------
这个仓库的检查散在四处:冒烟测试、实测值核对、GPU 目录核实、文档可达性。
单独跑哪一个都行,但没有一条命令能回答「现在这个仓库是不是还健康」,于是
每次改动都要靠人记住该跑哪些、跑没跑过。这个脚本把那套顺序固化下来,让
「检查」变成可以挂到定时任务上的动作,而不是一段口头流程。

两个模式
--------
默认(离线):不联网,只读仓库,秒级完成。任何一次改动后都能跑。
--online  :额外核实厂商页与权威文档链接是否还活着。慢,适合每天/每周一次。

退出码 = 失败项数(0 表示全通过)。SKIP 不算失败,但会单独列出来——
「跳过」和「通过」是两回事,不能让没跑的检查看起来像跑过了。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "ci"

#: AGENTS.md 硬约束:C: 可用空间低于这个值就必须停下所有会写盘的工作。
C_DRIVE_MIN_GIB = 20.0

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class Report:
    """收集结果。每个检查只有三种结局:通过 / 失败 / 跳过(附原因)。"""

    def __init__(self):
        self.rows = []

    def add(self, name, outcome, detail="", seconds=None):
        self.rows.append({"name": name, "outcome": outcome,
                          "detail": detail, "seconds": seconds})
        mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "warn": "WARN"}[outcome]
        timing = " (%.1fs)" % seconds if seconds is not None else ""
        print("  %-4s %-40s %s%s" % (mark, name, detail, timing))

    @property
    def failures(self):
        return [row for row in self.rows if row["outcome"] == "fail"]

    @property
    def skipped(self):
        return [row for row in self.rows if row["outcome"] == "skip"]

    def counts(self):
        return {kind: sum(1 for row in self.rows if row["outcome"] == kind)
                for kind in ("pass", "fail", "skip", "warn")}


def run(argv, timeout=900, cwd=ROOT):
    """跑一条命令并连输出一起捕获。绝不抛异常,失败由调用方判定。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    started = datetime.now()
    try:
        result = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout, env=env)
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output, (datetime.now() - started).total_seconds()
    except FileNotFoundError as error:
        return None, "命令不存在:%s" % error, 0.0
    except subprocess.TimeoutExpired:
        return None, "超时(%ds)" % timeout, (datetime.now() - started).total_seconds()


# --- 各项检查 -----------------------------------------------------------------

#: 这些目录里放的是别人家的代码(下载来的第三方源码、依赖、缓存、临时目录)。
#: 它们的语法问题不是本项目的缺陷,拿它们当门禁只会让 CI 常年红着,
#: 最后所有人都学会忽略结果——那比没有 CI 更糟。
THIRD_PARTY_PARTS = {"node_modules", "__pycache__", "source-cache", "vendor-sources",
                     ".git", ".venv", "site-packages"}


def is_third_party(relative_path):
    """判断路径是不是第三方/临时内容,门禁跳过它们。"""
    for part in relative_path.parts:
        if part in THIRD_PARTY_PARTS:
            return True
        # 隐藏目录(如 .vendor-fetch-cutlass-v4.4.2 / .tmp)一律跳过。
        if part.startswith("."):
            return True
    return False


def check_disk(report):
    """C: 盘余量门禁。

    这条不是形式主义:AGENTS.md 规定 C: 低于 20 GiB 必须停掉一切会写盘的工作,
    而本项目的离线包、镜像 tar、模型权重动辄十几 GB。让 CI 先说清楚磁盘状态,
    比等到某次构建中途写满盘要好。
    """
    try:
        import shutil
        gi = [("C", shutil.disk_usage("C:/")), ]
        for letter in ("D", "E"):
            try:
                gi.append((letter, shutil.disk_usage("%s:/" % letter)))
            except OSError:
                pass
    except OSError as error:
        report.add("C: 盘可用空间", "skip", "无法读取:%s" % error)
        return
    free = {letter: usage.free / (1024 ** 3) for letter, usage in gi}
    detail = " · ".join("%s: %.1f GiB" % (letter, value) for letter, value in free.items())
    if free.get("C", 0.0) < C_DRIVE_MIN_GIB:
        report.add("C: 盘可用空间", "fail",
                   "%s(低于 %.0f GiB 红线,先处理磁盘再跑会写盘的步骤)" % (detail, C_DRIVE_MIN_GIB))
    else:
        report.add("C: 盘可用空间", "pass", detail)


def check_python_compile(report):
    """先做语法检查。语法错误会让后面每一项都失败,先隔离出来最省时间。"""
    targets = []
    for folder in ("tools", "deploy-portal", "model-selector"):
        targets += [str(path) for path in sorted((ROOT / folder).rglob("*.py"))
                    if "__pycache__" not in path.parts]
    if not targets:
        report.add("Python 语法检查", "skip", "没有找到 .py 文件")
        return
    code, output, seconds = run([sys.executable, "-m", "py_compile"] + targets)
    if code == 0:
        report.add("Python 语法检查", "pass", "%d 个文件" % len(targets), seconds)
    else:
        report.add("Python 语法检查", "fail", output.strip().splitlines()[-1][:200], seconds)


def check_smoke(report):
    """主门禁。它自己会在进程内起服务并逐个打接口,是最能反映真实状态的一项。"""
    code, output, seconds = run([sys.executable, "deploy-portal/tools/smoke_test.py"])
    if code is None:
        report.add("冒烟测试", "fail", output, seconds)
        return
    passed = len(re.findall(r"^\s+PASS\s", output, re.M))
    failed = len(re.findall(r"^\s+FAIL\s", output, re.M))
    if failed:
        names = re.findall(r"^\s+FAIL\s+(.+)$", output, re.M)
        report.add("冒烟测试", "fail", "%d/%d 失败:%s" % (failed, passed + failed,
                                                       "、".join(names[:4])), seconds)
    else:
        report.add("冒烟测试", "pass", "%d 项全部通过" % passed, seconds)


def check_truth(report):
    """实测值核对:models.csv / model-families.csv 有没有被手改过。"""
    code, output, seconds = run([sys.executable, "deploy-portal/tools/apply_truth.py", "--check"])
    if code is None:
        report.add("实测值核对", "fail", output, seconds)
        return
    summary = re.search(r"汇总:.*", output)
    detail = summary.group(0) if summary else output.strip().splitlines()[-1][:160]
    if code != 0:
        report.add("实测值核对", "fail", detail, seconds)
    elif "改动" in detail and not detail.startswith("汇总:改动 0"):
        report.add("实测值核对", "fail", "登记值与实测不符:" + detail, seconds)
    else:
        report.add("实测值核对", "pass", detail, seconds)


def check_bash(report):
    """离线包的 shell 脚本做语法检查。

    这里必须先探测 bash 能不能读仓库路径:本机的 `bash` 实际是 WSL 的
    /bin/bash(未装发行版或未挂载该盘时会失败),它认的是 /mnt/d/... 而不是
    D:/...。第一次实现只探测了「bash 能不能跑 echo」,于是探测通过、紧接着
    每个脚本都报路径错误,把一项检查全判成失败——探测通过不等于这个用法可用。

    探测不到可用组合时如实报 SKIP,不报 PASS:一个没跑过的检查不能看起来像跑过了。
    """
    scripts = sorted(path for path in ROOT.rglob("*.sh")
                     if not is_third_party(path.relative_to(ROOT)))
    if not scripts:
        report.add("Shell 脚本语法", "skip", "没有找到 .sh 文件")
        return

    probe = ROOT / ".tmp" / "ci-bash-probe.sh"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text("#!/bin/sh\nset -eu\necho probe\n", encoding="utf-8")

    def wsl_path(path):
        """D:\\a\\b -> /mnt/d/a/b,供 WSL 里的 bash 使用。"""
        resolved = path.resolve()
        drive = resolved.drive.rstrip(":").lower()
        rest = resolved.as_posix().split(":", 1)[-1].lstrip("/")
        return "/mnt/%s/%s" % (drive, rest)

    bash = style = None
    for candidate in ("bash", "bash.exe"):
        for name, translate in (("posix", wsl_path), ("native", lambda item: item.as_posix())):
            code, output, _ = run([candidate, "-n", translate(probe)], timeout=30)
            if code == 0:
                bash, style, translate_path = candidate, name, translate
                break
        if bash:
            break
    try:
        probe.unlink()
    except OSError:
        pass
    if bash is None:
        report.add("Shell 脚本语法", "skip",
                   "%d 个脚本待检,本机 bash 读不到仓库路径(WSL 未挂载该盘?可装发行版或改用 WSL 内运行 CI)"
                   % len(scripts))
        return

    # bash -n 只做语法解析,不执行脚本,所以不会碰到离线包里的危险操作。
    bad = []
    for script in scripts:
        code, output, _ = run([bash, "-n", translate_path(script)], timeout=60)
        if code != 0:
            bad.append("%s: %s" % (script.relative_to(ROOT).as_posix(),
                                   output.strip().splitlines()[-1][:80]))
    if bad:
        report.add("Shell 脚本语法", "fail", "; ".join(bad[:3]))
    else:
        report.add("Shell 脚本语法", "pass",
                   "%d 个脚本(路径风格 %s)" % (len(scripts), style))


def check_catalog(report):
    """GPU 目录的自洽性:核实失败的条目不该被当成可用卡。"""
    path = ROOT / "deploy-portal" / "data" / "gpu-catalog.json"
    if not path.is_file():
        report.add("GPU 目录自洽", "fail", "缺少 %s" % path.name)
        return
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    gpus = snapshot.get("gpus") or []
    failed = [gpu["id"] for gpu in gpus if (gpu.get("verification") or {}).get("status") != "ok"]
    if not gpus:
        report.add("GPU 目录自洽", "fail", "目录里没有卡")
    elif failed:
        report.add("GPU 目录自洽", "fail", "核实未通过:%s" % "、".join(failed[:4]))
    else:
        vendors = {}
        for gpu in gpus:
            vendors[gpu.get("vendor") or "nvidia"] = vendors.get(gpu.get("vendor") or "nvidia", 0) + 1
        report.add("GPU 目录自洽", "pass",
                   "%d 张卡全部核实通过(%s)" % (len(gpus),
                   "、".join("%s %d" % (key, value) for key, value in sorted(vendors.items()))))


def check_residue(report):
    """根目录残留物只报 WARN。

    这些是用户自己的文件,CI 没有权力删;但每次跑都提一遍,免得临时脚本
    越积越多最后没人知道哪个还有用。
    """
    patterns = {
        "临时脚本(.tmp_*.py)": list(ROOT.glob(".tmp_*.py")),
        "待办/状态文件": list(ROOT.glob("*-PENDING.md")) + list(ROOT.glob("*-STATE.md")),
        "散落日志": list(ROOT.glob("*.log")) + list(ROOT.glob("build.log")),
    }
    hits = {name: files for name, files in patterns.items() if files}
    if not hits:
        report.add("根目录残留物", "pass", "未发现临时脚本/待办文件/散落日志")
        return
    detail = ";".join("%s %d 个" % (name, len(files)) for name, files in hits.items())
    report.add("根目录残留物", "warn", detail)


def check_replace_tool(report):
    """实测整文件替换工具本身。

    这个工具是改文件的必经之路,它坏掉会静默写坏文件,而不是报错。历史上已经
    栽过两次,所以这里拿真实的往返替换去测,而不是只做语法检查:

    1. 首行被改动时,旧实现把旧首行当补丁上下文,于是新首行被丢掉、旧首行留下;
    2. 校验失败要回滚时,旧实现用了 Python 3.8 不支持的 `write_text(newline=...)`,
       回滚自己抛 TypeError——比不回滚更糟,文件留在改了一半的状态;
    3. 新内容文件结尾没有换行时,更早的临时版本会静默丢掉最后一行,
       导致 `recommend.js` 少一个 `}`,整页停在「加载中」而接口全是 200。

    这三点都能被下面这一次往返替换覆盖。
    """
    script = ROOT / "deploy-portal" / "tools" / "whole_file_replace.py"
    if not script.is_file():
        report.add("整文件替换工具", "fail", "缺少 %s" % script.relative_to(ROOT).as_posix())
        return
    work = ROOT / ".tmp" / "ci-replace-check"
    work.mkdir(parents=True, exist_ok=True)
    target = work / "sample.txt"
    new_file = work / "sample.new.txt"
    # 旧内容首行与新内容不同(覆盖问题 1),且新内容结尾没有换行(覆盖问题 3)。
    target.write_text("OLD first line\nkeep me\nlast line\n", encoding="utf-8")
    expected = "NEW first line\nkeep me\nlast line"          # 故意不带结尾换行
    new_file.write_text(expected, encoding="utf-8")
    code, output, seconds = run([sys.executable, str(script.relative_to(ROOT)),
                                 str(target.relative_to(ROOT)),
                                 str(new_file.relative_to(ROOT))], timeout=120)
    try:
        actual = target.read_text(encoding="utf-8")
    except OSError as error:
        report.add("整文件替换工具", "fail", "读不回结果:%s" % error, seconds)
        return
    if code != 0:
        report.add("整文件替换工具", "fail",
                   "替换失败:%s" % output.strip().splitlines()[-1][:120], seconds)
    elif actual != expected + "\n":
        report.add("整文件替换工具", "fail",
                   "首行或结尾行没换对:得到 %r" % actual[:40], seconds)
    else:
        report.add("整文件替换工具", "pass", "往返替换逐字节一致", seconds)
    for path in (target, new_file):
        try:
            path.unlink()
        except OSError:
            pass


def check_project_files(report):
    """工作流自身的骨架是否还在。

    这些文件是「项目怎么运转」的载体:规则(AGENTS.md)、规范层、CI 入口、
    定时任务脚本、项目地图。它们被误删或被改名不会有任何报错,只会让下一个
    人(或下一个会话)找不到入口。所以在这里钉住。
    """
    required = {
        "AGENTS.md": "项目宪法:规则、边界、禁止事项",
        "docs/PROJECT-MAP.md": "项目地图:模块、入口、数据文件清单",
        "docs/CI.md": "持续集成与定时检查说明",
        "tools/ci.py": "CI 门禁本体",
        "scripts/ci/run-ci.ps1": "CI 包装脚本(留痕到 output/ci/)",
        "scripts/ci/register-scheduled-task.ps1": "定时任务注册脚本",
        ".github/workflows/ci.yml": "云端 CI",
    }
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        report.add("工作流骨架文件", "fail", "缺少:%s" % "、".join(sorted(missing)))
        return

    # 规范层的活规范:没有 spec 的 SDD 目录等于只有模板,形同虚设。
    specs = sorted((ROOT / ".codex-specs").glob("*/spec.md")) if (ROOT / ".codex-specs").is_dir() else []
    if not specs:
        report.add("工作流骨架文件", "warn",
                   "%d 个工作流文件齐全,但 .codex-specs/ 下还没有 spec.md" % len(required))
    else:
        report.add("工作流骨架文件", "pass",
                   "%d 个文件齐全,规范 %d 份" % (len(required), len(specs)))


def check_online(report):
    """联网核实:厂商页是否还逐字命中,权威文档链接是否还活着。"""
    code, output, seconds = run([sys.executable, "deploy-portal/tools/sync_gpus.py", "--check"],
                                timeout=900)
    if code is None:
        report.add("在线:GPU 厂商页核实", "fail", output, seconds)
    elif code == 0:
        line = next((item for item in output.splitlines() if "核实" in item and "通过" in item), "")
        report.add("在线:GPU 厂商页核实", "pass", line.strip()[:120], seconds)
    else:
        bad = [item.strip() for item in output.splitlines() if "FAIL" in item]
        report.add("在线:GPU 厂商页核实", "fail", "; ".join(bad[:3])[:200], seconds)

    code, output, seconds = run([sys.executable, "deploy-portal/tools/sync_docs.py", "--check"],
                                timeout=1800)
    if code is None:
        report.add("在线:权威文档可达性", "fail", output, seconds)
    elif code == 0:
        line = next((item for item in output.splitlines() if item.startswith("可达")), "")
        report.add("在线:权威文档可达性", "pass", line.strip()[:120], seconds)
    else:
        bad = [item.strip() for item in output.splitlines() if item.strip().startswith("FAIL")]
        report.add("在线:权威文档可达性", "fail", "; ".join(bad[:3])[:200], seconds)


def main(argv=None):
    parser = argparse.ArgumentParser(description="项目持续集成门禁")
    parser.add_argument("--online", action="store_true",
                        help="额外联网核实厂商页与权威文档链接")
    parser.add_argument("--json", metavar="PATH",
                        help="把结果写成 JSON 报告(供定时任务留痕)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    global print
    if args.quiet:
        print = lambda *a, **k: None  # noqa: E731

    started = datetime.now()
    print("项目 CI · %s · %s" % (started.strftime("%Y-%m-%d %H:%M:%S"),
                                 "含联网核实" if args.online else "离线检查"))
    print("-" * 72)

    report = Report()
    check_disk(report)
    check_python_compile(report)
    check_smoke(report)
    check_truth(report)
    check_bash(report)
    check_catalog(report)
    check_replace_tool(report)
    check_residue(report)
    check_project_files(report)
    if args.online:
        check_online(report)

    counts = report.counts()
    elapsed = (datetime.now() - started).total_seconds()
    print("-" * 72)
    print("通过 %d · 失败 %d · 跳过 %d · 提醒 %d(%.1fs)"
          % (counts["pass"], counts["fail"], counts["skip"], counts["warn"], elapsed))
    for row in report.skipped:
        print("  跳过:%s(%s)" % (row["name"], row["detail"]))
    for row in report.failures:
        print("  失败:%s(%s)" % (row["name"], row["detail"]))

    payload = {
        "started_at": started.strftime("%Y-%m-%dT%H:%M:%S"),
        "online": args.online,
        "seconds": round(elapsed, 1),
        "counts": counts,
        "checks": report.rows,
        "root": str(ROOT),
    }
    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print("报告写入 %s" % path)

    if counts["fail"]:
        print("结果:失败 %d 项" % counts["fail"])
    else:
        print("结果:全部通过")
    return counts["fail"]


if __name__ == "__main__":
    sys.exit(main())
