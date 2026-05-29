#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询相关的 MCP 工具
"""

import logging
from typing import Any, Dict
from pathlib import Path
from euclid_service.core.coordinate_matcher import query_tile_id, batch_query_tile_ids

logger = logging.getLogger(__name__)


async def handle_query_tile_id(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 query_tile_id 工具调用

    Args:
        arguments: 工具参数 {ra, dec, tile_index_file?}

    Returns:
        结果字典
    """
    try:
        ra = float(arguments['ra'])
        dec = float(arguments['dec'])
        tile_index_file = arguments.get('tile_index_file')

        tile_id = query_tile_id(ra, dec, tile_index_file)

        if tile_id is not None:
            return {
                'success': True,
                'ra': ra,
                'dec': dec,
                'tile_id': str(tile_id),
                'message': f'找到 TILE ID: {tile_id}'
            }
        else:
            return {
                'success': False,
                'ra': ra,
                'dec': dec,
                'tile_id': None,
                'message': '未找到对应的 TILE ID'
            }

    except Exception as e:
        logger.error(f"query_tile_id 执行失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'message': f'查询失败: {e}'
        }


async def handle_batch_query_tile_ids(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 batch_query_tile_ids 工具调用

    Args:
        arguments: 工具参数 {coordinates: [[ra, dec], ...], tile_index_file?}

    Returns:
        结果字典
    """
    try:
        coordinates = arguments['coordinates']
        tile_index_file = arguments.get('tile_index_file')

        # 转换为元组列表
        coord_list = [(float(coord[0]), float(coord[1])) for coord in coordinates]

        results = batch_query_tile_ids(coord_list, tile_index_file)

        return {
            'success': True,
            'num_queries': len(results),
            'results': results,
            'message': f'成功查询 {len(results)} 个坐标'
        }

    except Exception as e:
        logger.error(f"batch_query_tile_ids 执行失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'message': f'批量查询失败: {e}'
        }
