# 智构平台前端镜像：Vue 3 SPA 构建 + Nginx 静态服务与 API 反向代理
# 构建上下文为仓库根目录：docker build -f docker/frontend.Dockerfile -t agent-platform-frontend:local .
FROM node:22-alpine AS build

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/dist /usr/share/nginx/html

EXPOSE 80
