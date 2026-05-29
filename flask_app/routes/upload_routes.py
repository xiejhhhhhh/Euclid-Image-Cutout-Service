#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传路由 - 处理文件上传和模板服务
"""

import os
import time
import uuid
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify, send_from_directory, current_app

logger = logging.getLogger(__name__)

upload_bp = Blueprint('upload', __name__)


@upload_bp.route('/templates/<path:filename>')
def serve_template_file(filename):
    """提供模板文件服务"""
    template_dir = Path(__file__).parent.parent.parent / 'templates'
    return send_from_directory(template_dir, filename)


@upload_bp.route("/api/upload_file", methods=["POST"])
def upload_file():
    """上传星表文件到服务器"""
    try:
        # 获取上传的文件
        if 'catalog' not in request.files:
            return jsonify({'error': '没有找到星表文件'}), 400

        file = request.files['catalog']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400

        # 检查文件类型
        if not file.filename.endswith('.fits'):
            return jsonify({'error': '只支持FITS格式的星表文件'}), 400

        # 生成临时ID用于标识上传的文件
        temp_id = str(uuid.uuid4())
        temp_filename = f"{temp_id}.fits"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], temp_filename)

        # 保存文件
        file.save(file_path)

        # 验证文件是否成功保存（处理Linux文件系统延迟问题）
        retry_count = 0
        max_retries = 5
        file_exists = False

        while retry_count < max_retries:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                file_exists = True
                break
            retry_count += 1
            time.sleep(0.2)  # 等待200ms后重试

        if not file_exists:
            raise Exception("文件保存失败，无法验证文件是否成功写入磁盘")

        file_size = os.path.getsize(file_path)
        logger.info(f"文件已上传: {file.filename} 保存为临时文件 {temp_filename} (大小: {file_size} bytes)")

        return jsonify({
            'success': True,
            'filename': file.filename,  # 返回原始文件名给前端显示
            'temp_id': temp_id,  # 返回临时ID用于后续任务提交
            'file_size': file_size,
            'message': '文件上传成功'
        })
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        return jsonify({'error': f'文件上传失败: {str(e)}'}), 500
