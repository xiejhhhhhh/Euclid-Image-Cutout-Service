# Euclid 图像裁剪服务使用指南
[![Python 3.6+](https://img.shields.io/badge/Python-3.6%2B-3776AB?style=flat-square&logo=python&logoColor=white)](./requirements.txt)
[![Flask](https://img.shields.io/badge/Flask-Web%20Service-000000?style=flat-square&logo=flask&logoColor=white)](#)
[![FITS](https://img.shields.io/badge/FITS-Astronomy%20Catalog-5C4D7D?style=flat-square)](#)
[![Euclid Q1](https://img.shields.io/badge/Euclid-Q1-3A506B?style=flat-square)](#)
[![Batch Cutout](https://img.shields.io/badge/Batch-Image%20Cutout-4C956C?style=flat-square)](#)
[![Parallel Processing](https://img.shields.io/badge/Parallel-Processing-E07A5F?style=flat-square)](#)
[![Online Service](https://img.shields.io/badge/NADC-Online%20Service-1D7874?style=flat-square)](https://nadc.china-vo.org/mwr/euclid-imagecutout/)

[English](./README.md) | [中文](./README_CN.md)

## 项目概述

Euclid 图像裁剪服务是一个基于Flask的Web应用程序，用于从Euclid和其他天文数据集中批量裁剪天体图像。该服务支持上传FITS格式的星表，根据指定的坐标和参数自动裁剪图像，并支持波段缓存功能以提高处理效率。

相关工作已整理成网页工具，方便用户在线使用，无需本地部署。

主要功能：
- 批量上传FITS星表并处理多个天体目标
- 支持多种天文仪器和波段选择
- 可选择多种文件类型进行裁剪（BGSUB、FLAG、BGMOD等）
- 波段缓存机制，避免重复处理相同目标
- 任务状态跟踪和结果下载
- 并行处理以提高效率

## 安装说明

### 环境要求

- **操作系统**：Linux（推荐Ubuntu 18.04+）
- **Python**：3.6+
- **依赖包**：见requirements.txt
- **数据要求**：服务器中需内置Euclid Q1数据集
- **NADC平台支持**：感谢国家天文数据中心（NADC）平台支持

### 安装步骤

1. 克隆或下载项目代码

2. 安装依赖包
```bash
pip install -r requirements.txt
```

3. 配置数据路径

在`Euclid_flash_app.py`中配置以下路径：
```python
DATA_ROOT = Path("/data/astrodata/mirror/102042-Euclid-Q1")  # Euclid数据根目录
UPLOAD_DIR = '/data/home/xiejh/app_data/'  # 用户文件上传目录
PERMANENT_DOWNLOAD_DIR = '/data/home/xiejh/Euclid_download/'  # 波段缓存目录
```

4. 启动服务
```bash
python Euclid_flash_app.py
```

服务默认运行在 http://localhost:5000

## 前端使用指南

### 1. 上传星表

1. 点击"选择星表文件"按钮，上传FITS格式的星表文件（最大支持10,000行）
2. 确认赤经列名和赤纬列名设置正确（默认为"RA"和"DEC"）
3. 点击"上传文件"按钮，等待文件上传完成

### 2. 配置裁剪参数

1. **文件类型**：选择需要裁剪的文件类型
   - BGSUB（背景减去图像）- 默认为选中
   - CATALOG-PSF（PSF目录）- 默认为选中
   - FLAG（标志文件）
   - BGMOD（背景模型）
   - RMS（均方根文件）

2. **仪器选择**：选择天文仪器（单选）
   - VIS（可见光仪器）- 默认为选中
   - NISP（近红外光谱仪）
   - DECAM（暗能量相机）
   - HSC（超新星猎人相机）
   - GPC（千兆像素相机）
   - MEGACAM（大视场相机）

3. **波段选择**：根据所选仪器自动显示可用波段，可多选

4. **并行工作数**：设置并行处理的工作线程数（默认为4，范围1-16）

### 3. 提交和管理任务

1. 点击"提交任务"按钮开始处理
2. 在"任务列表"中查看任务状态
3. 任务完成后，点击"下载结果"获取ZIP格式的裁剪图像

## 星表格式要求

### 支持的文件格式

仅支持FITS格式的星表文件。

### 必需的列信息

星表必须包含以下列或可通过界面配置指定的列：

1. **赤经（RA）**：天体的赤经坐标，格式为度（decimal degrees）
2. **赤纬（DEC）**：天体的赤纬坐标，格式为度（decimal degrees）

### 可选的列信息

1. **TARGETID**：目标天体的唯一标识符。如果提供，系统将使用此ID来匹配波段缓存文件

### 星表格式示例

以下是一个符合要求的简单星表示例（以CSV格式展示结构）：

| TARGETID | RA        | DEC       |
|----------|-----------|-----------|
| 12345    | 150.12345 | 2.34567   |
| 12346    | 150.23456 | 2.45678   |
| 12347    | 150.34567 | 2.56789   |

### 星表限制

- 文件大小：无严格限制，但过大的文件可能导致处理时间过长
- 行数限制：最多支持10,000行数据

## 波段缓存功能

### 缓存原理

波段缓存是一种机制，用于存储已处理过的图像裁剪结果，避免重复处理相同的目标。系统会将处理结果保存到按波段分类的目录中，下次处理相同目标时可直接使用缓存文件。

### 缓存目录结构

```
/data/home/xiejh/Euclid_download/
├── VIS/            # VIS波段的缓存文件
├── NIR-Y/          # NIR-Y波段的缓存文件
├── NIR-J/          # NIR-J波段的缓存文件
├── NIR-H/          # NIR-H波段的缓存文件
├── DES-G/          # DES-G波段的缓存文件
├── DES-R/          # DES-R波段的缓存文件
├── DES-I/          # DES-I波段的缓存文件
├── DES-Z/          # DES-Z波段的缓存文件
└── ...             # 其他波段
```

### 缓存检索规则

系统根据以下规则检索缓存文件：
1. 根据TARGETID匹配文件名中包含相同ID的文件
2. 根据文件类型标识识别对应的文件类型
3. 波段通过缓存文件所在的目录确定

### 缓存优先级

1. 首先检查波段缓存目录中是否存在匹配的文件
2. 如果找到，直接使用缓存文件，提高处理速度
3. 如果未找到，执行正常的图像裁剪处理
4. 处理完成后，自动将结果备份到相应的波段缓存目录

## 后端API接口

### 1. 文件上传

```
POST /api/upload_file
Content-Type: multipart/form-data

参数：
- catalog: FITS格式的星表文件
```

响应：
```json
{
  "success": true,
  "temp_id": "临时文件ID",
  "filename": "上传的文件名",
  "message": "文件上传成功"
}
```

### 2. 提交任务

```
POST /api/submit_task
Content-Type: application/json

参数：
{
  "temp_id": "临时文件ID",
  "ra_col": "赤经列名",
  "dec_col": "赤纬列名",
  "size": 128,
  "file_types": ["BGSUB", "CATALOG-PSF"],
  "instrument": "VIS",
  "bands": ["VIS"],
  "n_workers": 4
}
```

响应：
```json
{
  "success": true,
  "task_id": "任务ID",
  "message": "任务已提交"
}
```

### 3. 获取任务状态

```
GET /api/task_status?task_id=任务ID
```

响应：
```json
{
  "task_id": "任务ID",
  "status": "completed", // queued, processing, completed, failed
  "progress": 100,
  "message": "任务处理完成",
  "result_url": "下载链接"
}
```

## 常见问题与故障排除

### 文件上传失败
- 确保上传的是FITS格式文件
- 检查文件大小，过大的文件可能需要更长时间

### 任务处理失败
- 检查星表格式是否正确，特别是RA和DEC列
- 确认选择的仪器和波段组合是否有效
- 查看服务器日志获取详细错误信息

### 缓存文件不匹配
- 确保星表中包含正确的TARGETID列
- 检查缓存文件命名是否符合规范，应包含TARGETID

## 性能优化建议

1. 对于大量目标的批处理，建议适当增加并行工作数（n_workers）
2. 优先使用波段缓存功能，避免重复处理
3. 对于频繁处理的目标，确保提供TARGETID以提高缓存命中率
4. 处理前先检查波段缓存目录，确认已有缓存文件的状态

## 技术支持

如有任何问题或建议，请联系系统管理员。
<div align="center">


</div>
