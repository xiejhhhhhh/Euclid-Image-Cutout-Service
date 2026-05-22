<div align="center">

[![Python 3.6+](https://img.shields.io/badge/Python-3.6%2B-3776AB?style=flat-square&logo=python&logoColor=white)](./requirements.txt)
[![Flask](https://img.shields.io/badge/Flask-Web%20Service-000000?style=flat-square&logo=flask&logoColor=white)](#)
[![FITS](https://img.shields.io/badge/FITS-Astronomy%20Catalog-5C4D7D?style=flat-square)](#)
[![Euclid Q1](https://img.shields.io/badge/Euclid-Q1-3A506B?style=flat-square)](#)
[![Batch Cutout](https://img.shields.io/badge/Batch-Image%20Cutout-4C956C?style=flat-square)](#)
[![Parallel Processing](https://img.shields.io/badge/Parallel-Processing-E07A5F?style=flat-square)](#)
[![Online Service](https://img.shields.io/badge/NADC-Online%20Service-1D7874?style=flat-square)](https://nadc.china-vo.org/mwr/euclid-imagecutout/)

# Euclid 图像裁剪服务使用指南

[English](./README.md) | [中文](./README_CN.md)

</div>

## 项目概览

Euclid 图像裁剪服务是一个基于 Flask 的 Web 应用，用于从 Euclid 及其他天文数据集中批量裁剪天体图像。该服务支持上传 FITS 格式星表，根据指定坐标和参数自动裁剪图像，并提供波段缓存机制以提高处理效率。

相关工作已经整理为在线 Web 工具，用户无需本地部署即可直接使用。服务默认运行地址为：
[(https://nadc.china-vo.org/mwr/euclid-imagecutout/)](https://nadc.china-vo.org/mwr/euclid-imagecutout/)

主要功能：
- 批量上传 FITS 星表并处理多个天体目标
- 支持多种天文仪器与波段选择
- 可选择多种裁剪文件类型（BGSUB、FLAG、BGMOD 等）
- 通过波段缓存机制避免重复处理相同目标
- 支持任务状态跟踪与结果下载
- 支持并行处理以提高效率

## 安装说明

### 环境要求

- **操作系统**：Linux（推荐 Ubuntu 18.04+）
- **Python**：3.6+
- **依赖包**：见 `requirements.txt`
- **数据要求**：服务器中需预置 Euclid Q1 数据集
- **NADC 平台支持**：感谢国家天文科学数据中心（NADC）的平台支持

### 安装步骤

1. 克隆或下载项目代码

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置数据路径

在 `Euclid_flash_app.py` 中配置如下路径：
```python
DATA_ROOT = Path("/data/astrodata/mirror/102042-Euclid-Q1")  # Euclid 数据根目录
UPLOAD_DIR = '/data/home/xiejh/app_data/'  # 用户文件上传目录
PERMANENT_DOWNLOAD_DIR = '/data/home/xiejh/Euclid_download/'  # 波段缓存目录
```

4. 启动服务
```bash
python Euclid_flash_app.py
```

## 前端使用指南

### 1. 上传星表

1. 点击 “Select Catalog File” 按钮上传 FITS 格式星表文件（最大支持 10,000 行）
2. 确认赤经（RA）和赤纬（DEC）列名设置正确（默认分别为 “RA” 和 “DEC”）
3. 点击 “Upload File” 按钮并等待文件上传完成

### 2. 配置裁剪参数

1. **文件类型**：选择需要裁剪的文件类型
   - BGSUB（背景减除图像）- 默认选中
   - CATALOG-PSF（PSF 星表）- 默认选中
   - FLAG（标记文件）
   - BGMOD（背景模型）
   - RMS（均方根文件）

2. **仪器选择**：选择一个天文仪器（单选）
   - VIS（可见光仪器）- 默认选中
   - NISP（近红外成像/光谱仪）
   - DECAM（暗能量相机）
   - HSC（Hyper Suprime-Cam）
   - GPC（Gigapixel Camera）
   - MEGACAM（MegaPrime Camera）

3. **波段选择**：系统会根据所选仪器自动显示可用波段，支持多选

4. **并行工作数**：设置并行处理线程数（默认 4，范围 1-16）

### 3. 提交与管理任务

1. 点击 “Submit Task” 按钮开始处理
2. 在 “Task List” 中查看任务状态
3. 任务完成后点击 “Download Results” 下载 ZIP 格式裁剪结果

## 星表格式要求

### 支持的文件格式

仅支持 FITS 格式星表文件。

### 必需列信息

星表必须包含以下列，或包含可通过界面配置指定的对应列：

1. **Right Ascension (RA)**：天体赤经坐标，单位为十进制度
2. **Declination (DEC)**：天体赤纬坐标，单位为十进制度

### 可选列信息

1. **TARGETID**：目标天体唯一标识。如果提供，系统将使用该 ID 匹配波段缓存文件

### 星表示例

下面是一个符合要求的简单星表示例（以 CSV 结构展示）：

| TARGETID | RA        | DEC       |
|----------|-----------|-----------|
| 12345    | 150.12345 | 2.34567   |
| 12346    | 150.23456 | 2.45678   |
| 12347    | 150.34567 | 2.56789   |

### 星表限制

- 文件大小：无严格限制，但文件过大可能导致处理时间变长
- 行数限制：最多支持 10,000 行数据

## 波段缓存功能

### 缓存原理

波段缓存是一种用于存储已处理图像裁剪结果的机制，可避免对相同目标进行重复处理。系统会将处理结果保存到按波段分类的目录中，下次处理相同目标时可直接复用缓存文件。

### 缓存目录结构

```
/data/home/xiejh/Euclid_download/
├── VIS/            # VIS 波段缓存文件
├── NIR-Y/          # NIR-Y 波段缓存文件
├── NIR-J/          # NIR-J 波段缓存文件
├── NIR-H/          # NIR-H 波段缓存文件
├── DES-G/          # DES-G 波段缓存文件
├── DES-R/          # DES-R 波段缓存文件
├── DES-I/          # DES-I 波段缓存文件
├── DES-Z/          # DES-Z 波段缓存文件
└── ...             # 其他波段
```

### 缓存检索规则

系统按照以下规则检索缓存文件：
1. 根据 TARGETID 匹配文件名中包含相同 ID 的文件
2. 根据文件类型标识识别对应文件类型
3. 通过缓存文件所在目录判断所属波段

### 缓存优先级

1. 首先检查波段缓存目录中是否存在匹配文件
2. 如果存在，则直接使用缓存文件以提高处理速度
3. 如果不存在，则执行正常的图像裁剪流程
4. 处理完成后，结果会自动备份到对应波段的缓存目录中

## 后端 API 接口

### 1. 文件上传

```
POST /api/upload_file
Content-Type: multipart/form-data

Parameters:
- catalog: FITS format catalog file
```

响应：
```json
{
  "success": true,
  "temp_id": "temporary_file_id",
  "filename": "uploaded_filename",
  "message": "File uploaded successfully"
}
```

### 2. 提交任务

```
POST /api/submit_task
Content-Type: application/json

Parameters:
{
  "temp_id": "temporary_file_id",
  "ra_col": "ra_column_name",
  "dec_col": "dec_column_name",
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
  "task_id": "task_id",
  "message": "Task submitted"
}
```

### 3. 获取任务状态

```
GET /api/task_status?task_id=task_id
```

响应：
```json
{
  "task_id": "task_id",
  "status": "completed", // queued, processing, completed, failed
  "progress": 100,
  "message": "Task processing completed",
  "result_url": "download_url"
}
```

## 常见问题与排查

### 文件上传失败
- 确认上传文件为 FITS 格式
- 检查文件大小，过大文件可能需要更长上传时间

### 任务处理失败
- 检查星表格式是否正确，尤其是 RA 和 DEC 列
- 确认所选仪器与波段组合有效
- 查看服务器日志以获取详细错误信息

### 缓存文件不匹配
- 确认星表中包含正确的 TARGETID 列
- 检查缓存文件命名是否符合规范，文件名中应包含 TARGETID

## 性能优化建议

1. 当需要批量处理大量目标时，建议适当增加并行工作数（`n_workers`）
2. 优先使用波段缓存机制，避免重复处理
3. 对于经常处理的目标，建议提供 TARGETID 以提高缓存命中率
4. 在正式处理前，先检查波段缓存目录中的已有缓存状态

## 技术支持

如果你有任何问题或建议，请联系系统管理员。
