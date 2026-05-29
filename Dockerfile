# Euclid Image Cutout Service Dockerfile
# 包含 Flask App (端口 5000) 和 MCP SSE 服务 (端口 8000)

FROM m.daocloud.io/docker.io/library/python:3.12-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 配置 pip 使用国内镜像源并安装 Python 依赖
RUN unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    sse-starlette \
    mcp

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p /app/outputs /app/cache /app/tmp /app/data /app/templates /app/static

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 5000 8000

# 创建启动脚本
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "=========================================================="\n\
echo "🚀 启动 Euclid Image Cutout Service"\n\
echo "=========================================================="\n\
echo "📡 Flask App: http://0.0.0.0:5000"\n\
echo "📡 MCP SSE Server: http://0.0.0.0:8000"\n\
echo "=========================================================="\n\
\n\
# 启动 Flask App (后台)\n\
python /app/run_flask.py &\n\
FLASK_PID=$!\n\
echo "✅ Flask App 已启动 (PID: $FLASK_PID)"\n\
\n\
# 启动 MCP SSE Server (前台)\n\
python /app/run_mcp_sse.py &\n\
MCP_PID=$!\n\
echo "✅ MCP SSE Server 已启动 (PID: $MCP_PID)"\n\
\n\
# 等待进程\n\
wait -n\n\
\n\
# 如果任一进程退出，杀死另一个\n\
kill $FLASK_PID $MCP_PID 2>/dev/null\n\
exit $?\n\
' > /app/start.sh && chmod +x /app/start.sh

# 健康检查（使用 Python 而不是 curl）
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health'); urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 启动服务
CMD ["/app/start.sh"]
