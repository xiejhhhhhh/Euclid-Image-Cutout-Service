#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Euclid Image Cutout Service - Flask Application
"""

import os
from pathlib import Path
from flask import Flask
from flask_cors import CORS

from euclid_service.config import get_config
from euclid_service.logging_config import setup_logging

# 初始化日志
logger = setup_logging()

# 加载配置
config = get_config()

# 创建 Flask 应用
app = Flask(__name__,
            template_folder='../templates',
            static_folder='../static')

# 配置 CORS
CORS(app)

# 配置应用
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB
app.config['UPLOAD_FOLDER'] = config.get('workspace.upload_dir', '/home/aaron/tmp')
app.config['OUTPUT_FOLDER'] = Path(__file__).parent.parent / 'outputs'
app.config['CACHE_FOLDER'] = Path(__file__).parent.parent / 'cache'
app.config['TMP_FOLDER'] = Path(__file__).parent.parent / 'tmp'

# 确保目录存在
for folder in ['UPLOAD_FOLDER', 'OUTPUT_FOLDER', 'CACHE_FOLDER', 'TMP_FOLDER']:
    Path(app.config[folder]).mkdir(parents=True, exist_ok=True)

# 注册路由蓝图
from flask_app.routes.upload_routes import upload_bp
from flask_app.routes.task_routes import task_bp
from flask_app.routes.health_routes import health_bp

app.register_blueprint(upload_bp)
app.register_blueprint(task_bp)
app.register_blueprint(health_bp)

logger.info("Flask 应用初始化完成")

if __name__ == '__main__':
    host = config.get('flask.host', '0.0.0.0')
    port = config.get('flask.port', 5000)
    debug = config.get('flask.debug', False)

    logger.info(f"启动 Flask 服务器: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
