# 智构平台 API / Worker 镜像
# 构建：docker build -f docker/platform-api.Dockerfile -t agent-platform-api:local ..
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先装依赖，利用构建缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码（config.py 以 base_dir=/app 解析 data/skills 等路径）
COPY alembic.ini ./
COPY app ./app
COPY skills ./skills

# 非 root 运行；/app/data 由卷挂载，命名卷首次挂载会继承镜像目录属主
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
