#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星表数据模型
定义星表相关的数据结构
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import numpy as np


@dataclass
class CatalogInfo:
    """星表信息"""
    id: str
    file_path: str
    num_rows: int
    ra_col: str
    dec_col: str
    target_id_col: Optional[str] = None
    ra_range: Optional[tuple] = None  # (min, max)
    dec_range: Optional[tuple] = None  # (min, max)
    columns: List[str] = None
    file_size: int = 0  # 字节
    format: str = "fits"  # fits 或 csv

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'file_path': self.file_path,
            'num_rows': self.num_rows,
            'ra_col': self.ra_col,
            'dec_col': self.dec_col,
            'target_id_col': self.target_id_col,
            'ra_range': list(self.ra_range) if self.ra_range else None,
            'dec_range': list(self.dec_range) if self.dec_range else None,
            'columns': self.columns,
            'file_size': self.file_size,
            'format': self.format
        }


@dataclass
class CoordinateMatch:
    """坐标匹配结果"""
    ra: float
    dec: float
    matched_id: Optional[str] = None
    separation_arcsec: Optional[float] = None
    matched: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'ra': self.ra,
            'dec': self.dec,
            'matched_id': self.matched_id,
            'separation_arcsec': self.separation_arcsec,
            'matched': self.matched
        }


@dataclass
class CatalogValidationResult:
    """星表验证结果"""
    valid: bool
    errors: List[str]
    warnings: List[str]
    num_rows: int
    num_valid_coords: int
    num_invalid_coords: int

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'valid': self.valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'num_rows': self.num_rows,
            'num_valid_coords': self.num_valid_coords,
            'num_invalid_coords': self.num_invalid_coords
        }
