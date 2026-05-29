#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务处理器 - 封装任务创建和处理逻辑
"""

import uuid
import threading
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from euclid_service.core.task_executor import TaskExecutor
from euclid_service.config import get_config

logger = logging.getLogger(__name__)

# 加载配置
config = get_config()


class TaskProcessor:
    """任务处理器类"""

    def __init__(self, tasks_dict: Dict, tasks_lock: threading.Lock):
        """
        初始化任务处理器

        Args:
            tasks_dict: 任务字典
            tasks_lock: 任务字典的线程锁
        """
        self.tasks = tasks_dict
        self.tasks_lock = tasks_lock

    def create_task(self, catalog_path: str, task_config: Dict[str, Any]) -> str:
        """
        创建新任务

        Args:
            catalog_path: 星表文件路径
            task_config: 任务配置

        Returns:
            task_id: 任务ID
        """
        task_id = str(uuid.uuid4())

        # 初始化任务状态
        with self.tasks_lock:
            self.tasks[task_id] = {
                'task_id': task_id,
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'catalog_path': catalog_path,
                'config': task_config,
                'progress': 0,
                'message': '任务已创建，等待处理'
            }

        # 在后台线程中处理任务
        executor = TaskExecutor(
            task_id=task_id,
            catalog_path=catalog_path,
            task_config=task_config,
            tasks_dict=self.tasks,
            tasks_lock=self.tasks_lock
        )

        thread = threading.Thread(
            target=executor.execute,
            daemon=True
        )
        thread.start()

        logger.info(f"任务 {task_id} 已创建并开始处理")

        return task_id

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态字典
        """
        with self.tasks_lock:
            if task_id not in self.tasks:
                return None
            return self.tasks[task_id].copy()

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务（标记为取消，实际处理可能继续）

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        with self.tasks_lock:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]
            if task['status'] in ['completed', 'failed']:
                return False

            task['status'] = 'cancelled'
            task['message'] = '任务已取消'

        logger.info(f"任务 {task_id} 已标记为取消")
        return True

    def list_tasks(self) -> list:
        """
        列出所有任务

        Returns:
            任务列表
        """
        with self.tasks_lock:
            return [
                {
                    'task_id': task_id,
                    'status': task['status'],
                    'created_at': task.get('created_at'),
                    'progress': task.get('progress', 0),
                    'message': task.get('message', '')
                }
                for task_id, task in self.tasks.items()
            ]
