#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志配置模块
提供统一的日志配置和管理
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional
from euclid_service.config import Config


def setup_logging(config: Optional[Config] = None, name: Optional[str] = None) -> logging.Logger:
    """
    配置日志系统，同时输出到控制台和文件

    Args:
        config: 配置对象（可选）
        name: 日志记录器名称（可选）

    Returns:
        配置好的日志记录器
    """
    # 获取日志配置
    if config is None:
        from euclid_service.config import get_config
        config = get_config()

    log_level = config.get('logging.level', 'INFO')
    log_dir = Path(config.get('logging.dir', '~/euclid_logs')).expanduser()
    max_file_size = config.get('logging.max_file_size_mb', 100) * 1024 * 1024  # 转换为字节
    backup_count = config.get('logging.backup_count', 10)
    log_format = config.get('logging.format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 创建日志目录
    log_dir.mkdir(parents=True, exist_ok=True)

    # 生成日志文件名（按日期）
    log_filename = log_dir / f"euclid_{datetime.now().strftime('%Y%m%d')}.log"

    # 创建或获取日志记录器
    if name:
        logger = logging.getLogger(name)
    else:
        logger = logging.getLogger()

    # 设置日志级别
    logger.setLevel(getattr(logging, log_level.upper()))

    # 清除现有的处理器（避免重复）
    if not logger.handlers:
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_formatter = logging.Formatter(
            log_format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)

        # 创建文件处理器（支持日志轮转）
        file_handler = logging.handlers.RotatingFileHandler(
            log_filename,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_formatter = logging.Formatter(
            log_format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)

        # 添加处理器到日志记录器
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        日志记录器
    """
    return logging.getLogger(name)


def configure_module_logger(module_name: str, config: Optional[Config] = None) -> logging.Logger:
    """
    为特定模块配置日志记录器

    Args:
        module_name: 模块名称
        config: 配置对象（可选）

    Returns:
        配置好的日志记录器
    """
    return setup_logging(config, module_name)


# 全局日志记录器实例
_global_logger: Optional[logging.Logger] = None


def init_logging(config: Optional[Config] = None) -> logging.Logger:
    """
    初始化全局日志系统

    Args:
        config: 配置对象（可选）

    Returns:
        全局日志记录器
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = setup_logging(config)
    return _global_logger


def get_global_logger() -> logging.Logger:
    """获取全局日志记录器"""
    global _global_logger
    if _global_logger is None:
        _global_logger = init_logging()
    return _global_logger
