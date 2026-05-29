#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星表相关的 MCP 工具
"""

import logging
from typing import Any, Dict
from pathlib import Path
from euclid_service.core.catalog_processor import load_catalog, get_catalog_statistics

logger = logging.getLogger(__name__)


async def handle_get_catalog_info(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 get_catalog_info 工具调用

    Args:
        arguments: 工具参数 {catalog_path, ra_col?, dec_col?, id_col?}

    Returns:
        结果字典
    """
    try:
        catalog_path = arguments['catalog_path']
        ra_col = arguments.get('ra_col')
        dec_col = arguments.get('dec_col')
        id_col = arguments.get('id_col')

        # 加载星表
        catalog, detected_ra_col, detected_dec_col, detected_id_col = load_catalog(
            catalog_path, ra_col, dec_col, id_col
        )

        # 获取统计信息
        stats = get_catalog_statistics(catalog, detected_ra_col, detected_dec_col)

        # 获取文件信息
        file_path = Path(catalog_path)
        file_size = file_path.stat().st_size if file_path.exists() else 0

        return {
            'success': True,
            'catalog_path': str(catalog_path),
            'file_size': file_size,
            'file_size_mb': round(file_size / 1024 / 1024, 2),
            'ra_col': detected_ra_col,
            'dec_col': detected_dec_col,
            'id_col': detected_id_col,
            'statistics': stats,
            'message': f'成功加载星表，共 {stats["num_rows"]} 行'
        }

    except Exception as e:
        logger.error(f"get_catalog_info 执行失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'message': f'获取星表信息失败: {e}'
        }


async def handle_validate_catalog(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 validate_catalog 工具调用

    Args:
        arguments: 工具参数 {catalog_path, ra_col?, dec_col?, max_rows?}

    Returns:
        结果字典
    """
    try:
        catalog_path = arguments['catalog_path']
        ra_col = arguments.get('ra_col')
        dec_col = arguments.get('dec_col')
        max_rows = arguments.get('max_rows', 10000)

        # 加载星表
        catalog, detected_ra_col, detected_dec_col, detected_id_col = load_catalog(
            catalog_path, ra_col, dec_col
        )

        # 验证
        errors = []
        warnings = []

        # 检查行数
        if len(catalog) > max_rows:
            errors.append(f'星表行数 ({len(catalog)}) 超过限制 ({max_rows})')

        # 获取统计信息
        stats = get_catalog_statistics(catalog, detected_ra_col, detected_dec_col)

        # 检查有效坐标比例
        if stats['num_invalid_coords'] > 0:
            invalid_ratio = stats['num_invalid_coords'] / stats['num_rows']
            if invalid_ratio > 0.1:
                warnings.append(f'无效坐标比例较高: {invalid_ratio:.1%}')

        # 检查坐标范围
        if stats['ra_range']:
            ra_min, ra_max = stats['ra_range']
            if ra_min < 0 or ra_max > 360:
                warnings.append(f'RA 范围异常: [{ra_min}, {ra_max}]')

        if stats['dec_range']:
            dec_min, dec_max = stats['dec_range']
            if dec_min < -90 or dec_max > 90:
                warnings.append(f'DEC 范围异常: [{dec_min}, {dec_max}]')

        valid = len(errors) == 0

        return {
            'success': True,
            'valid': valid,
            'errors': errors,
            'warnings': warnings,
            'statistics': stats,
            'message': '验证通过' if valid else f'验证失败: {len(errors)} 个错误'
        }

    except Exception as e:
        logger.error(f"validate_catalog 执行失败: {e}", exc_info=True)
        return {
            'success': False,
            'valid': False,
            'error': str(e),
            'message': f'验证失败: {e}'
        }
