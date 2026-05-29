#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星表处理模块（简化版）
提供星表加载和基本处理功能
"""

import logging
from pathlib import Path
from typing import Optional, Tuple, List
from astropy.io import fits
from astropy.table import Table
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def load_catalog(
    catalog_path: str,
    ra_col: Optional[str] = None,
    dec_col: Optional[str] = None,
    id_col: Optional[str] = None
) -> Tuple[Table, str, str, Optional[str]]:
    """
    加载星表文件（FITS或CSV格式）

    Args:
        catalog_path: 星表文件路径
        ra_col: RA列名（可选，自动检测）
        dec_col: DEC列名（可选，自动检测）
        id_col: ID列名（可选，自动检测）

    Returns:
        (catalog, ra_col, dec_col, id_col)
    """
    catalog_path = Path(catalog_path)

    if not catalog_path.exists():
        raise FileNotFoundError(f"星表文件不存在: {catalog_path}")

    # 根据文件扩展名加载
    if catalog_path.suffix.lower() in ['.fits', '.fit']:
        catalog = Table.read(catalog_path, format='fits')
    elif catalog_path.suffix.lower() in ['.csv', '.txt']:
        catalog = Table.from_pandas(pd.read_csv(catalog_path))
    else:
        raise ValueError(f"不支持的文件格式: {catalog_path.suffix}")

    # 自动检测列名
    columns = [col.upper() for col in catalog.colnames]

    # 检测 RA 列
    if ra_col is None:
        ra_candidates = ['RA', 'RA_DEG', 'ALPHA_J2000', 'ALPHAWIN_J2000']
        for candidate in ra_candidates:
            if candidate in columns:
                ra_col = catalog.colnames[columns.index(candidate)]
                break
        if ra_col is None:
            raise ValueError("无法自动检测RA列，请手动指定")

    # 检测 DEC 列
    if dec_col is None:
        dec_candidates = ['DEC', 'DEC_DEG', 'DELTA_J2000', 'DELTAWIN_J2000']
        for candidate in dec_candidates:
            if candidate in columns:
                dec_col = catalog.colnames[columns.index(candidate)]
                break
        if dec_col is None:
            raise ValueError("无法自动检测DEC列，请手动指定")

    # 检测 ID 列
    if id_col is None:
        id_candidates = ['TARGETID', 'TARGET_ID', 'ID', 'SOURCE_ID', 'NUMBER']
        for candidate in id_candidates:
            if candidate in columns:
                id_col = catalog.colnames[columns.index(candidate)]
                break

    logger.info(f"加载星表: {catalog_path}, 行数: {len(catalog)}, RA列: {ra_col}, DEC列: {dec_col}, ID列: {id_col}")

    return catalog, ra_col, dec_col, id_col


def get_catalog_statistics(catalog: Table, ra_col: str, dec_col: str) -> dict:
    """
    获取星表统计信息

    Args:
        catalog: 星表数据
        ra_col: RA列名
        dec_col: DEC列名

    Returns:
        统计信息字典
    """
    ra_data = catalog[ra_col]
    dec_data = catalog[dec_col]

    # 过滤有效坐标
    valid_mask = np.isfinite(ra_data) & np.isfinite(dec_data)
    valid_ra = ra_data[valid_mask]
    valid_dec = dec_data[valid_mask]

    stats = {
        'num_rows': len(catalog),
        'num_valid_coords': int(np.sum(valid_mask)),
        'num_invalid_coords': int(len(catalog) - np.sum(valid_mask)),
        'ra_range': [float(np.min(valid_ra)), float(np.max(valid_ra))] if len(valid_ra) > 0 else None,
        'dec_range': [float(np.min(valid_dec)), float(np.max(valid_dec))] if len(valid_dec) > 0 else None,
        'ra_mean': float(np.mean(valid_ra)) if len(valid_ra) > 0 else None,
        'dec_mean': float(np.mean(valid_dec)) if len(valid_dec) > 0 else None,
        'columns': catalog.colnames
    }

    return stats
