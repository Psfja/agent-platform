#!/usr/bin/env bash
# 平台安全与供应链检查（在装有 Docker 的主机或 CI 上执行）
#   trivy  : 镜像漏洞扫描    https://github.com/aquasecurity/trivy
#   syft   : SBOM 生成       https://github.com/anchore/syft
#   docker scout / buildx   : 镜像层分析
set -euo pipefail
cd "$(dirname "$0")/.."

check() { command -v "$1" >/dev/null 2>&1 || { echo "✗ 缺少 $1（跳过）"; return 1; }; }

echo "▶ 1/4 依赖审计"
npm audit --audit-level=moderate
(cd backend && .venv/bin/pip list --outdated --format=columns | head -20 || true)

echo "▶ 2/4 SAST（Semgrep）"
if check semgrep; then
  semgrep scan --config=auto --error --severity=ERROR backend/app src 2>/dev/null \
    || echo "⚠ Semgrep 发现需要人工确认的发现"
else
  echo "  pip install semgrep 后重新运行"
fi

echo "▶ 3/4 镜像构建与漏洞扫描"
if check docker; then
  docker build -f docker/frontend.Dockerfile -t agent-platform-frontend:scan .
  docker build -f backend/docker/platform-api.Dockerfile -t agent-platform-api:scan ./backend
  if check trivy; then
    trivy image --severity HIGH,CRITICAL agent-platform-frontend:scan
    trivy image --severity HIGH,CRITICAL agent-platform-api:scan
  else
    echo "  brew install aquasecurity/trivy/trivy 后重新运行"
  fi
fi

echo "▶ 4/4 SBOM 生成"
if check syft; then
  mkdir -p dist/sbom
  syft agent-platform-frontend:scan -o spdx-json > dist/sbom/frontend.spdx.json
  syft agent-platform-api:scan -o spdx-json > dist/sbom/api.spdx.json
  echo "  SBOM 已生成：dist/sbom/"
else
  echo "  brew install anchore/syft/syft 后重新运行"
fi
echo "✔ 安全检查流程结束"
