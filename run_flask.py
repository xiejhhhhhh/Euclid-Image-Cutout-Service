#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动 Euclid Flask Web 应用
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    from flask_app.app import app
    from euclid_service.config import get_config

    # 加载配置
    try:
        config = get_config()
        host = config.get('flask.host', '0.0.0.0')
        port = config.get('flask.port', 5000)
        debug = config.get('flask.debug', False)
    except Exception as e:
        print(f"警告: 无法加载配置文件，使用默认值: {e}")
        host = '0.0.0.0'
        port = 5000
        debug = False

    print("=" * 60)
    print("🚀 启动 Euclid Image Cutout Flask 服务")
    print("=" * 60)
    print(f"📡 服务地址: http://{host}:{port}")
    print(f"🔧 健康检查: http://{host}:{port}/health")
    print(f"🌐 Web 界面: http://{host}:{port}/")
    print("=" * 60)
    print("\n按 Ctrl+C 停止服务器\n")

    # 启动服务器
    app.run(host=host, port=port, debug=debug, threaded=True)
