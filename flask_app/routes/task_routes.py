#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务路由 - 处理任务提交、状态查询、下载等
"""

import os
import logging
import threading
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app

from euclid_service.core.task_processor import TaskProcessor

logger = logging.getLogger(__name__)

task_bp = Blueprint('task', __name__)

# 任务字典和锁
tasks = {}
tasks_lock = threading.Lock()

# 创建任务处理器实例
task_processor = TaskProcessor(tasks, tasks_lock)


@task_bp.route('/api/submit_task', methods=['POST'])
def submit_task():
    """提交任务处理"""
    try:
        # 获取临时文件ID和原始文件名
        temp_id = request.form.get('temp_id')
        original_filename = request.form.get('filename')

        if not temp_id:
            return jsonify({'error': '缺少临时文件ID'}), 400

        # 构建临时文件路径
        temp_filename = f"{temp_id}.fits"
        catalog_path = os.path.join(current_app.config['UPLOAD_FOLDER'], temp_filename)

        # 验证文件是否存在
        if not os.path.exists(catalog_path):
            return jsonify({'error': '临时文件不存在，请重新上传'}), 400

        # 获取任务配置参数
        config = {
            'ra_col': request.form.get('ra_col', 'RA'),
            'dec_col': request.form.get('dec_col', 'DEC'),
            'target_id_col': request.form.get('target_id_col', 'TARGETID'),
            'size': int(request.form.get('size', 128)),
            'instruments': request.form.getlist('instruments') or ['VIS', 'NIR', 'MER'],
            'file_types': request.form.getlist('file_types') or ['SCI', 'WHT', 'RMS'],
            'band': request.form.get('band', 'VIS'),  # 使用单数 band 以兼容原始代码
            'n_workers': min(int(request.form.get('max_workers', 4)), 16),  # 使用 n_workers 以兼容原始代码
            'original_filename': original_filename
        }

        # 创建任务
        task_id = task_processor.create_task(catalog_path, config)

        logger.info(f"任务已创建: {task_id}, 配置: {config}")

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '任务已提交'
        })

    except Exception as e:
        logger.error(f"任务提交失败: {str(e)}", exc_info=True)
        return jsonify({'error': f'任务提交失败: {str(e)}'}), 500


@task_bp.route('/api/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    with tasks_lock:
        if task_id not in tasks:
            return jsonify({'error': '任务不存在'}), 404

        task = tasks[task_id].copy()

    # 计算处理时间
    if task['status'] == 'completed' and 'start_time' in task and 'end_time' in task:
        try:
            start = datetime.fromisoformat(task['start_time'])
            end = datetime.fromisoformat(task['end_time'])
            task['processing_time'] = (end - start).total_seconds()
        except:
            pass

    return jsonify(task)


@task_bp.route('/api/download/<task_id>', methods=['GET'])
def download_result(task_id):
    """下载任务结果"""
    with tasks_lock:
        if task_id not in tasks:
            return jsonify({'error': '任务不存在'}), 404

        task = tasks[task_id]

        if task['status'] != 'completed':
            return jsonify({'error': '任务尚未完成'}), 400

        zip_path = task.get('zip_path')

    if not zip_path or not os.path.exists(zip_path):
        return jsonify({'error': '结果文件不存在'}), 404

    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f"{task_id}.zip",
        mimetype='application/zip'
    )


@task_bp.route('/api/tasks', methods=['GET'])
def list_tasks():
    """列出所有任务"""
    with tasks_lock:
        task_list = []
        for task_id, task in tasks.items():
            task_info = {
                'task_id': task_id,
                'status': task['status'],
                'created_at': task.get('created_at'),
                'progress': task.get('progress', 0),
                'message': task.get('message', '')
            }

            # 添加统计信息
            if 'stats' in task:
                task_info['stats'] = task['stats']

            task_list.append(task_info)

    # 按创建时间倒序排列
    task_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    return jsonify({
        'success': True,
        'tasks': task_list,
        'total': len(task_list)
    })
