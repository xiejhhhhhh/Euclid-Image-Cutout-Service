#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 MCP 图像裁剪工具
"""

import asyncio
import json
from pathlib import Path
from astropy.io import fits

# 导入 MCP 工具处理函数
from mcp_server.tools.cutout_tools import (
    handle_cutout_single,
    handle_cutout_batch,
    handle_get_cutout_status,
    handle_list_cutout_tasks
)

async def retrieve_object_id():
    with fits.open("/media/aaron/AARON/Euclid-Image-Cutout-Service/data/EuclidQ1_MER_catalog.fits") as hdul:
        # 查看文件结构
        hdul.info()
        
        # 读取包含数据的扩展(通常是第1个扩展)
        data = hdul[1].data
        
        # 查看 OBJECT_ID 列
        object_ids = data['OBJECT_ID']
        print("OBJECT_ID -> ")
        print(object_ids)
        

async def test_cutout_single():
    """测试单个坐标裁剪"""
    print("\n" + "="*60)
    print("测试 1: 单个坐标裁剪 (cutout_single)")
    print("="*60)

    # 测试参数
    arguments = {
        'ra': 150.0,
        'dec': 2.0,
        'size': 64,
        'instruments': ['VIS'],
        'file_types': ['SCI'],
        'obj_id': 'test_obj_001'
    }

    print(f"\n输入参数:")
    print(json.dumps(arguments, indent=2, ensure_ascii=False))

    # 调用工具
    result = await handle_cutout_single(arguments)

    print(f"\n返回结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return result


async def test_cutout_batch():
    """测试批量裁剪"""
    print("\n" + "="*60)
    print("测试 2: 批量裁剪 (cutout_batch)")
    print("="*60)

    # 创建测试星表
    from astropy.table import Table
    import numpy as np

    # 生成测试数据
    test_catalog = Table({
        'RA': [150.0, 150.1, 150.2],
        'DEC': [2.0, 2.1, 2.2],
        'TARGETID': [1, 2, 3]
    })

    # 保存到临时文件
    test_catalog_path = Path('./tmp/test_catalog.fits')
    test_catalog_path.parent.mkdir(parents=True, exist_ok=True)
    test_catalog.write(test_catalog_path, format='fits', overwrite=True)

    print(f"\n创建测试星表: {test_catalog_path}")
    print(f"包含 {len(test_catalog)} 个源")

    # 测试参数
    arguments = {
        'catalog_path': str(test_catalog_path),
        'ra_col': 'RA',
        'dec_col': 'DEC',
        'obj_id_col': 'TARGETID',
        'size': 64,
        'instruments': ['VIS'],
        'file_types': ['SCI'],
        'n_workers': 2
    }

    print(f"\n输入参数:")
    print(json.dumps(arguments, indent=2, ensure_ascii=False))

    # 调用工具
    result = await handle_cutout_batch(arguments)

    print(f"\n返回结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return result


async def test_get_cutout_status(task_id):
    """测试查询任务状态"""
    print("\n" + "="*60)
    print("测试 3: 查询任务状态 (get_cutout_status)")
    print("="*60)

    arguments = {
        'task_id': task_id
    }

    print(f"\n输入参数:")
    print(json.dumps(arguments, indent=2, ensure_ascii=False))

    # 调用工具
    result = await handle_get_cutout_status(arguments)

    print(f"\n返回结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return result


async def test_list_cutout_tasks():
    """测试列出所有任务"""
    print("\n" + "="*60)
    print("测试 4: 列出所有任务 (list_cutout_tasks)")
    print("="*60)

    arguments = {}

    # 调用工具
    result = await handle_list_cutout_tasks(arguments)

    print(f"\n返回结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return result


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("开始测试 MCP 图像裁剪工具")
    print("="*60)

    await retrieve_object_id()

    try:
        # 测试 1: 单个坐标裁剪
        result1 = await test_cutout_single()

        if result1['success']:
            print("\n✓ 测试 1 通过")
        else:
            print(f"\n✗ 测试 1 失败: {result1.get('error')}")

        # 测试 2: 批量裁剪
        result2 = await test_cutout_batch()

        if result2['success']:
            print("\n✓ 测试 2 通过")
            task_id = result2['task_id']

            # 等待一段时间让任务开始处理
            print("\n等待 2 秒...")
            await asyncio.sleep(2)

            # 测试 3: 查询任务状态
            result3 = await test_get_cutout_status(task_id)

            if result3['success']:
                print("\n✓ 测试 3 通过")
            else:
                print(f"\n✗ 测试 3 失败: {result3.get('error')}")
        else:
            print(f"\n✗ 测试 2 失败: {result2.get('error')}")

        # 测试 4: 列出所有任务
        result4 = await test_list_cutout_tasks()

        if result4['success']:
            print("\n✓ 测试 4 通过")
        else:
            print(f"\n✗ 测试 4 失败: {result4.get('error')}")

        print("\n" + "="*60)
        print("所有测试完成")
        print("="*60)

    except Exception as e:
        print(f"\n✗ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())
