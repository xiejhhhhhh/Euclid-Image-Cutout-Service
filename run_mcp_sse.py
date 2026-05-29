#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动 Euclid MCP 服务器 (SSE Transport)
专门为 N8N MCP Client 节点设计
"""

import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    import uvicorn
    from euclid_service.config import get_config

    # 加载配置
    try:
        config = get_config()
        host = config.get('mcp.host', '0.0.0.0')
        port = config.get('mcp.port', 8000)
    except Exception as e:
        print(f"警告: 无法加载配置文件，使用默认值: {e}")
        host = '0.0.0.0'
        port = 8000

    print("=" * 60)
    print("🚀 启动 Euclid Image Cutout MCP 服务器 (SSE Transport)")
    print("=" * 60)
    print(f"📡 服务地址: http://{host}:{port}")
    print(f"📡 SSE 端点: http://{host}:{port}/sse")
    print(f"📨 消息端点: http://{host}:{port}/message")
    print(f"🔧 健康检查: http://{host}:{port}/health")
    print("=" * 60)
    print("\n在 N8N 中配置 MCP Client 节点:")
    print(f"  - Transport: SSE")
    print(f"  - URL: http://{host}:{port}/sse")
    print("\n按 Ctrl+C 停止服务器\n")

    # 启动服务器
    uvicorn.run(
        "mcp_server.server_sse_v2:app",
        host=host,
        port=port,
        log_level="info",
        reload=False
    )
