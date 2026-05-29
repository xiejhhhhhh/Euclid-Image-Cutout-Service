#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
坐标查询模块（简化版）
提供坐标到TILE ID的查询功能
"""

import logging
from typing import Optional
from euclid_service.core.euclid_cutout_remix import query_tile_id as _query_tile_id

logger = logging.getLogger(__name__)


def query_tile_id(ra: float, dec: float, tile_index_file: Optional[str] = None) -> Optional[str]:
    """
    根据坐标查询TILE ID

    Args:
        ra: 赤经（度）
        dec: 赤纬（度）
        tile_index_file: TILE坐标文件路径（必需）

    Returns:
        TILE ID字符串，如果未找到则返回None
    """
    try:
        # 如果未指定文件，使用默认路径
        if tile_index_file is None:
            from pathlib import Path
            tile_index_file = str(Path(__file__).parent.parent.parent / "data/EuclidQ1_tile_coordinates.fits")

        # 调用底层函数
        tile_id = _query_tile_id(ra, dec, tile_index_file=tile_index_file)
        logger.info(f"查询坐标 ({ra}, {dec}) -> TILE ID: {tile_id}")
        return tile_id
    except Exception as e:
        logger.error(f"查询TILE ID失败: {e}")
        return None


def batch_query_tile_ids(coordinates: list, tile_index_file: Optional[str] = None) -> list:
    """
    批量查询TILE ID

    Args:
        coordinates: 坐标列表 [(ra1, dec1), (ra2, dec2), ...]
        tile_index_file: TILE坐标文件路径（可选）

    Returns:
        TILE ID列表
    """
    results = []
    for ra, dec in coordinates:
        tile_id = query_tile_id(ra, dec, tile_index_file)
        results.append({
            'ra': ra,
            'dec': dec,
            'tile_id': tile_id
        })
    return results
