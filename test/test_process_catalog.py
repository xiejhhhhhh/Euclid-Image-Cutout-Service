#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 process_catalog 函数
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from astropy.table import Table
from euclid_service.core.euclid_cutout_remix import process_catalog

# 测试参数
catalog_path = "/media/aaron/AARON/Euclid-Image-Cutout-Service/data/EuclidQ1_MER_catalog.fits"  # 你的测试文件路径
output_dir = "/tmp/test_output"
tile_index_file = str(Path(__file__).parent / 'data' / 'EuclidQ1_tile_coordinates.fits')
mer_root = "/media/aaron/DATA/astro+euclid/mirror/euclid_q1_102042/MER"

# 加载星表
catalog = Table.read(catalog_path)
print(f"星表行数: {len(catalog)}")
print(f"星表列: {catalog.colnames}")

# 只取前5行测试
test_catalog = catalog[:5]

# 调用 process_catalog
print("\n开始测试 process_catalog...")
result = process_catalog(
    catalog=test_catalog,
    output_dir=output_dir,
    file_types=['SCI'],
    ra_col='RIGHT_ASCENSION',
    dec_col='DECLINATION',
    size=128,
    obj_id_col='OBJECT_ID',
    tile_index_file=tile_index_file,
    mer_root=mer_root,
    instruments=['VIS'],
    bands=['VIS'],
    skip_nan=True,
    save_catalog_row=True,
    parallel=False,  # 单线程便于调试
    n_workers=1,
    verbose=True  # 开启详细输出
)

print("\n处理结果:")
print(result)
