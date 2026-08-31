#!/usr/bin/env bash
# 一键端到端验收：启动后端 → 运行 Playwright → 清理
# 依赖：backend/.venv 已安装 requirements-dev.txt；npx playwright install chromium（首次）
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▶ 启动后端 (SQLite, 端口 8000)"
(cd backend && DATABASE_URL=sqlite:///./data/e2e.db .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &) 
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -sf http://localhost:8000/health >/dev/null || { echo "后端启动失败"; exit 1; }

echo "▶ 运行 Playwright"
npm run test:e2e

kill "$BACKEND_PID" 2>/dev/null || true
trap - EXIT
echo "✔ E2E 完成"
