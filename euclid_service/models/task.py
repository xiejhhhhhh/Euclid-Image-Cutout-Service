#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务数据模型
定义任务状态和相关数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid


class TaskStatus(Enum):
    """任务状态枚举"""
    QUEUED = "queued"          # 排队中
    PROCESSING = "processing"   # 处理中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"     # 已取消


@dataclass
class TaskStats:
    """任务统计信息"""
    total_sources: int = 0
    cached_sources: int = 0
    new_sources: int = 0
    errors: int = 0
    permanent_cached: int = 0
    failed_targets: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Task:
    """任务数据模型"""
    id: str
    status: TaskStatus
    catalog_id: str
    catalog_path: str
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    progress: float = 0.0
    message: str = ""
    stats: Optional[TaskStats] = None
    zip_path: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def create(cls, catalog_id: str, catalog_path: str, config: Dict[str, Any]) -> 'Task':
        """
        创建新任务

        Args:
            catalog_id: 星表ID
            catalog_path: 星表文件路径
            config: 任务配置

        Returns:
            Task实例
        """
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            status=TaskStatus.QUEUED,
            catalog_id=catalog_id,
            catalog_path=catalog_path,
            config=config,
            created_at=now,
            updated_at=now,
            stats=TaskStats()
        )

    def update_status(self, status: TaskStatus, message: str = ""):
        """更新任务状态"""
        self.status = status
        self.message = message
        self.updated_at = datetime.now()

    def update_progress(self, progress: float, message: str = ""):
        """更新任务进度"""
        self.progress = progress
        if message:
            self.message = message
        self.updated_at = datetime.now()

    def mark_completed(self, zip_path: str):
        """标记任务完成"""
        self.status = TaskStatus.COMPLETED
        self.progress = 100.0
        self.zip_path = zip_path
        self.updated_at = datetime.now()

    def mark_failed(self, error: str):
        """标记任务失败"""
        self.status = TaskStatus.FAILED
        self.error = error
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'status': self.status.value,
            'catalog_id': self.catalog_id,
            'catalog_path': self.catalog_path,
            'config': self.config,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'progress': self.progress,
            'message': self.message,
            'stats': {
                'total_sources': self.stats.total_sources if self.stats else 0,
                'cached_sources': self.stats.cached_sources if self.stats else 0,
                'new_sources': self.stats.new_sources if self.stats else 0,
                'errors': self.stats.errors if self.stats else 0,
                'permanent_cached': self.stats.permanent_cached if self.stats else 0,
                'failed_targets': self.stats.failed_targets if self.stats else []
            } if self.stats else None,
            'zip_path': self.zip_path,
            'error': self.error
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """从字典创建任务"""
        stats_data = data.get('stats')
        stats = TaskStats(**stats_data) if stats_data else None

        return cls(
            id=data['id'],
            status=TaskStatus(data['status']),
            catalog_id=data['catalog_id'],
            catalog_path=data['catalog_path'],
            config=data['config'],
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            progress=data.get('progress', 0.0),
            message=data.get('message', ''),
            stats=stats,
            zip_path=data.get('zip_path'),
            error=data.get('error')
        )
