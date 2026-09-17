#!/usr/bin/env bash
# 按现场Ubuntu codename补齐Docker CE与NVIDIA Container Toolkit。
# 已满足条件时默认跳过;永不自动安装system/driver下的.run驱动。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="${PKG:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
SYSTEM_DIR="${PKG}/system"
FORCE_DOCKER_INSTALL="${FORCE_DOCKER_INSTALL:-0}"
MIN_DRIVER="${MIN_DRIVER:-545.0}"

[ "${EUID}" -eq 0 ] || {
  echo "!! 请使用:sudo env PKG=${PKG} bash ${SCRIPT_DIR}/install-system-deps.sh"
  exit 1
}
[ "$(uname -m)" = "x86_64" ] || { echo "!! 只支持x86_64"; exit 1; }
[ -r /etc/os-release ] || { echo "!! 无/etc/os-release"; exit 1; }
. /etc/os-release
CODENAME="${VERSION_CODENAME:-}"
case "${ID:-}:${CODENAME}" in
  ubuntu:focal|ubuntu:jammy|ubuntu:noble) ;;
  *) echo "!! 未准备${ID:-unknown}/${CODENAME:-unknown}的离线包;停止安装"; exit 1 ;;
esac

offline_apt_install() {
  apt-get \
    -o Dir::Etc::sourcelist=/dev/null \
    -o Dir::Etc::sourceparts=- \
    -o APT::Get::List-Cleanup=0 \
    install -y "$@"
}

version_ge() {
  [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

# 只把PACKAGES.lock列出的文件交给apt,并先核对上游索引记录的SHA256。
LOCKED_DEBS=()
load_locked_debs() {
  local dir="$1" expected_count="$2" name version file expected actual
  local lock="${dir}/PACKAGES.lock"
  [ -r "${lock}" ] || { echo "!! 缺少${lock}"; exit 1; }
  LOCKED_DEBS=()
  while IFS='|' read -r name version file expected; do
    [ -n "${expected:-}" ] || continue
    [[ "${expected}" =~ ^[0-9a-fA-F]{64}$ ]] || { echo "!! ${lock}哈希格式无效:${file}"; exit 1; }
    [ -f "${dir}/${file}" ] || { echo "!! 缺少${dir}/${file}"; exit 1; }
    actual="$(sha256sum "${dir}/${file}" | awk '{print $1}')"
    [ "${actual,,}" = "${expected,,}" ] || { echo "!! SHA256不匹配:${dir}/${file}"; exit 1; }
    LOCKED_DEBS+=("${dir}/${file}")
  done < "${lock}"
  [ "${#LOCKED_DEBS[@]}" -eq "${expected_count}" ] || {
    echo "!! ${lock}应有${expected_count}个包,实际${#LOCKED_DEBS[@]}个"
    exit 1
  }
}

echo "== 系统:${PRETTY_NAME:-$ID} codename=${CODENAME} arch=$(uname -m) =="
if command -v nvidia-smi >/dev/null 2>&1; then
  DRIVER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1 | tr -d '[:space:]')"
  echo "driver=${DRIVER}"
  version_ge "${DRIVER}" "${MIN_DRIVER}" || {
    echo "!! 驱动${DRIVER}<${MIN_DRIVER},停止部署。driver/.run只能在独立维护窗口人工安装"
    exit 1
  }
else
  echo "!! 无nvidia-smi。driver/.run仅为人工兜底,本脚本不会自动装驱动"
fi

docker_ready() { command -v docker >/dev/null 2>&1 && docker version >/dev/null 2>&1; }
if docker_ready && [ "${FORCE_DOCKER_INSTALL}" != "1" ]; then
  echo "PASS:Docker已可用,保留现有版本"
else
  if command -v docker >/dev/null 2>&1 && [ "${FORCE_DOCKER_INSTALL}" != "1" ]; then
    systemctl enable --now docker 2>/dev/null || true
  fi
  if ! docker_ready || [ "${FORCE_DOCKER_INSTALL}" = "1" ]; then
    DOCKER_DIR="${SYSTEM_DIR}/docker/${CODENAME}"
    load_locked_debs "${DOCKER_DIR}" 5
    DOCKER_DEBS=("${LOCKED_DEBS[@]}")
    echo "== 安装${CODENAME}专用Docker CE包 =="
    offline_apt_install "${DOCKER_DEBS[@]}" || {
      echo "!! Docker本地deb依赖不满足。不要联网补包;记录错误后回准备机补齐"
      exit 1
    }
    systemctl enable --now docker
  fi
fi
docker_ready || { echo "!! Docker daemon不可用"; exit 1; }

runtime_ready() {
  docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -qi nvidia
}
if runtime_ready; then
  echo "PASS:NVIDIA runtime已配置,保留现有版本"
else
  TOOLKIT_DIR="${SYSTEM_DIR}/nvidia-container-toolkit"
  load_locked_debs "${TOOLKIT_DIR}" 4
  TOOLKIT_DEBS=("${LOCKED_DEBS[@]}")
  echo "== 安装NVIDIA Container Toolkit =="
  offline_apt_install "${TOOLKIT_DEBS[@]}" || {
    echo "!! Toolkit本地deb依赖不满足;停止"
    exit 1
  }
  command -v nvidia-ctk >/dev/null 2>&1 || { echo "!! 安装后仍无nvidia-ctk"; exit 1; }
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker
fi
runtime_ready || { echo "!! NVIDIA runtime仍不可用"; exit 1; }

echo "PASS:系统容器依赖已就绪。下一步:sudo env PKG=${PKG} bash ${SCRIPT_DIR}/install-offline.sh"
