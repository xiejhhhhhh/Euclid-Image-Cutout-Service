#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图像裁剪相关的 MCP 工具
提供单个坐标裁剪、批量裁剪、任务状态查询等功能
"""

import logging
import os
import uuid
import threading
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

from astropy.table import Table
from astropy.io import fits
import numpy as np

from euclid_service.config import get_config
from euclid_service.core.task_processor import TaskProcessor
from euclid_service.core.euclid_cutout_remix import (
    query_tile_id,
    cutout_tile,
    save_cutouts
)

logger = logging.getLogger(__name__)

# 加载配置
config = get_config()

# 任务字典和锁（用于 MCP 工具）
mcp_tasks = {}
mcp_tasks_lock = threading.Lock()

# 创建任务处理器实例
task_processor = TaskProcessor(mcp_tasks, mcp_tasks_lock)


async def handle_cutout_single(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理单个坐标的图像裁剪

    Args:
        arguments: 工具参数 {
            ra: float,
            dec: float,
            size: int (default: 128),
            instruments: List[str] (default: ['VIS']),
            file_types: List[str] (default: ['SCI', 'WHT']),
            bands: List[str] (optional),
            output_dir: str (optional),
            obj_id: str (optional)
        }

    Returns:
        结果字典，包含裁剪结果路径或错误信息
    """
    try:
        # 解析参数
        ra = float(arguments['ra'])
        dec = float(arguments['dec'])
        size = int(arguments.get('size', 128))
        instruments = arguments.get('instruments', ['VIS'])
        file_types = arguments.get('file_types', ['SCI', 'WHT'])
        bands = arguments.get('bands')
        obj_id = arguments.get('obj_id', f'obj_{ra:.4f}_{dec:.4f}')

        # 输出目录
        output_dir = arguments.get('output_dir')
        if not output_dir:
            output_dir = Path(config.get('workspace.tmp_dir', './tmp')) / 'mcp_cutouts' / str(uuid.uuid4())
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始单个坐标裁剪: RA={ra}, DEC={dec}, size={size}")

        # 查询 TILE ID
        tile_index_file = str(Path(__file__).parent.parent.parent / 'data' / 'EuclidQ1_tile_coordinates.fits')
        tile_id = query_tile_id(ra, dec, tile_index_file)

        if not tile_id:
            return {
                'success': False,
                'error': f'无法找到坐标 ({ra}, {dec}) 对应的 TILE ID',
                'message': '该坐标可能不在 Euclid Q1 覆盖范围内'
            }

        logger.info(f"找到 TILE ID: {tile_id}")

        # MER 数据根目录
        mer_root = str(Path(config.get('data.root')) / 'MER')

        # 对每个文件类型进行裁剪
        results = {}
        cutout_files = []

        for file_type in file_types:
            try:
                # 执行裁剪
                cutout_result = cutout_tile(
                    tile_id=tile_id,
                    ra=ra,
                    dec=dec,
                    size=size,
                    file_type=file_type,
                    mer_root=mer_root,
                    instruments=instruments,
                    bands=bands,
                    skip_nan=True
                )

                if cutout_result['success']:
                    # 保存裁剪结果
                    file_output_dir = output_dir / file_type
                    file_output_dir.mkdir(parents=True, exist_ok=True)
                    output_path = file_output_dir / f"{obj_id}.fits"

                    success = save_cutouts(
                        output_path=str(output_path),
                        cutouts_result=cutout_result,
                        obj_id=obj_id,
                        catalog_row=None,
                        verbose=True
                    )

                    if success:
                        results[file_type] = {
                            'success': True,
                            'file_path': str(output_path),
                            'num_cutouts': len(cutout_result['cutouts'])
                        }
                        cutout_files.append(str(output_path))
                    else:
                        results[file_type] = {
                            'success': False,
                            'error': '保存文件失败'
                        }
                else:
                    results[file_type] = {
                        'success': False,
                        'error': cutout_result.get('error', 'Unknown error')
                    }

            except Exception as e:
                logger.error(f"裁剪 {file_type} 失败: {e}", exc_info=True)
                results[file_type] = {
                    'success': False,
                    'error': str(e)
                }

        # 统计成功和失败的数量
        success_count = sum(1 for r in results.values() if r['success'])
        failed_count = len(results) - success_count

        return {
            'success': success_count > 0,
            'ra': ra,
            'dec': dec,
            'tile_id': tile_id,
            'obj_id': obj_id,
            'output_dir': str(output_dir),
            'results': results,
            'cutout_files': cutout_files,
            'summary': {
                'total': len(file_types),
                'success': success_count,
                'failed': failed_count
            },
            'message': f'成功裁剪 {success_count}/{len(file_types)} 个文件类型'
        }

    except Exception as e:
        logger.error(f"cutout_single 执行失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'message': f'单个坐标裁剪失败: {e}'
        }


async def handle_cutout_batch(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理批量坐标的图像裁剪（异步任务）

    Args:
        arguments: 工具参数 {
            catalog_path: str (FITS 或 CSV 文件路径),
            ra_col: str (default: 'RA'),
            dec_col: str (default: 'DEC'),
            obj_id_col: str (optional),
            size: int (default: 128),
            instruments: List[str] (default: ['VIS']),
            file_types: List[str] (default: ['SCI', 'WHT']),
            bands: List[str] (optional),
            n_workers: int (default: 4),
            max_rows: int (default: 10000)
        }

    Returns:
        任务信息字典，包含 task_id 用于后续查询
    """
    try:
        # 解析参数
        catalog_path = arguments['catalog_path']

        if not os.path.exists(catalog_path):
            return {
                'success': False,
                'error': f'星表文件不存在: {catalog_path}',
                'message': '请提供有效的星表文件路径'
            }

        # 任务配置
        task_config = {
            'ra_col': arguments.get('ra_col', 'RA'),
            'dec_col': arguments.get('dec_col', 'DEC'),
            'target_id_col': arguments.get('obj_id_col'),
            'size': int(arguments.get('size', 128)),
            'instruments': arguments.get('instruments', ['VIS']),
            'file_types': arguments.get('file_types', ['SCI', 'WHT']),
            'band': arguments.get('bands', ['VIS'])[0] if arguments.get('bands') else 'VIS',
            'n_workers': min(int(arguments.get('n_workers', 4)), 16),
            'original_filename': os.path.basename(catalog_path)
        }

        logger.info(f"创建批量裁剪任务: {catalog_path}")
        logger.info(f"任务配置: {task_config}")

        # 创建任务
        task_id = task_processor.create_task(catalog_path, task_config)

        return {
            'success': True,
            'task_id': task_id,
            'catalog_path': catalog_path,
            'config': task_config,
            'message': f'批量裁剪任务已创建，任务ID: {task_id}',
            'note': '使用 get_cutout_status 工具查询任务状态'
        }

    except Exception as e:
        logger.error(f"cutout_batch 执行失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'message': f'批量裁剪任务创建失败: {e}'
        }


async def handle_get_cutout_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    查询裁剪任务状态

    Args:
        arguments: 工具参数 {
            task_id: str
        }

    Returns:
        任务状态字典
    """
    try:
        task_id = arguments['task_id']

        with mcp_tasks_lock:
            if task_id not in mcp_tasks:
                return {
                    'success': False,
                    'error': f'任务不存在: {task_id}',
                    'message': '请检查任务ID是否正确'
                }

            task = mcp_tasks[task_id].copy()

        # 计算处理时间
        if task['status'] == 'completed' and 'start_time' in task and 'end_time' in task:
            try:
                start = datetime.fromisoformat(task['start_time'])
                end = datetime.fromisoformat(task['end_time'])
                task['processing_time_seconds'] = (end - start).total_seconds()
            except:
                pass

        # 添加下载信息
        if task['status'] == 'completed' and 'zip_path' in task:
            zip_path = task['zip_path']
            if os.path.exists(zip_path):
                task['zip_size_mb'] = round(os.path.getsize(zip_path) / (1024 * 1024), 2)
                task['download_ready'] = True
            else:
                task['download_ready'] = False

        return {
            'success': True,
            'task': task,
            'message': f'任务状态: {task["status"]}'
        }

    except Exception as e:
        logger.error(f"get_cutout_status 执行失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'message': f'查询任务状态失败: {e}'
        }


async def handle_list_cutout_tasks(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    列出所有裁剪任务

    Args:
        arguments: 工具参数 {
            status_filter: str (optional, 'pending'/'processing'/'completed'/'failed')
        }

    Returns:
        任务列表
    """
    try:
        status_filter = arguments.get('status_filter')

        with mcp_tasks_lock:
            task_list = []
            for task_id, task in mcp_tasks.items():
                # 应用状态过滤
                if status_filter and task['status'] != status_filter:
                    continue

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

                # 添加配置信息
                if 'config' in task:
                    task_info['config'] = {
                        'instruments': task['config'].get('instruments'),
                        'file_types': task['config'].get('file_types'),
                        'size': task['config'].get('size')
                    }

                task_list.append(task_info)

        # 按创建时间倒序排列
        task_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return {
            'success': True,
            'tasks': task_list,
            'total': len(task_list),
            'filter': status_filter,
            'message': f'找到 {len(task_list)} 个任务'
        }

    except Exception as e:
        logger.error(f"list_cutout_tasks 执行失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'message': f'列出任务失败: {e}'
        }
