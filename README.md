# Euclid Image Cutout Service User Guide

## Project Overview

Euclid Image Cutout Service is a Flask-based web application for batch cropping astronomical images from Euclid and other astronomical datasets. The service supports uploading FITS format catalogs, automatically cropping images based on specified coordinates and parameters, and features a band caching mechanism to improve processing efficiency.

Related work has been organized into a web tool, allowing users to access it online without local deployment.

Key Features:
- Batch upload FITS catalogs and process multiple celestial targets
- Support for multiple astronomical instruments and band selection
- Selectable file types for cropping (BGSUB, FLAG, BGMOD, etc.)
- Band caching mechanism to avoid repeated processing of the same targets
- Task status tracking and result download
- Parallel processing for improved efficiency

## Installation Instructions

### Environment Requirements

- **Operating System**: Linux (Ubuntu 18.04+ recommended)
- **Python**: 3.6+
- **Dependencies**: See requirements.txt
- **Data Requirements**: Euclid Q1 dataset must be built into the server
- **NADC Platform Support**: Thanks to the support of National Astronomical Data Center (NADC)

### Installation Steps

1. Clone or download the project code

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure data paths

Configure the following paths in `Euclid_flash_app.py`:
```python
DATA_ROOT = Path("/data/astrodata/mirror/102042-Euclid-Q1")  # Euclid data root directory
UPLOAD_DIR = '/data/home/xiejh/app_data/'  # User file upload directory
PERMANENT_DOWNLOAD_DIR = '/data/home/xiejh/Euclid_download/'  # Band cache directory
```

4. Start the service
```bash
python Euclid_flash_app.py
```

The service runs by default at [(https://nadc.china-vo.org/mwr/euclid-imagecutout/)]

## Frontend Usage Guide

### 1. Upload Catalog

1. Click the "Select Catalog File" button to upload a FITS format catalog file (maximum 10,000 rows)
2. Confirm that the Right Ascension (RA) and Declination (DEC) column names are set correctly (default is "RA" and "DEC")
3. Click the "Upload File" button and wait for the file upload to complete

### 2. Configure Cropping Parameters

1. **File Types**: Select the file types to crop
   - BGSUB (Background Subtracted Image) - selected by default
   - CATALOG-PSF (PSF Catalog) - selected by default
   - FLAG (Flag File)
   - BGMOD (Background Model)
   - RMS (Root Mean Square File)

2. **Instrument Selection**: Select an astronomical instrument (single choice)
   - VIS (Visible Light Instrument) - selected by default
   - NISP (Near-Infrared Spectrometer)
   - DECAM (Dark Energy Camera)
   - HSC (Hyper Suprime-Cam)
   - GPC (Gigapixel Camera)
   - MEGACAM (MegaPrime Camera)

3. **Band Selection**: Available bands are automatically displayed based on the selected instrument, multiple selection allowed

4. **Number of Parallel Workers**: Set the number of parallel processing threads (default is 4, range 1-16)

### 3. Submit and Manage Tasks

1. Click the "Submit Task" button to start processing
2. Check the task status in the "Task List"
3. After the task is completed, click "Download Results" to get the cropped images in ZIP format

## Catalog Format Requirements

### Supported File Formats

Only FITS format catalog files are supported.

### Required Column Information

The catalog must contain the following columns or columns that can be specified through the interface configuration:

1. **Right Ascension (RA)**: Celestial object's right ascension coordinate in decimal degrees
2. **Declination (DEC)**: Celestial object's declination coordinate in decimal degrees

### Optional Column Information

1. **TARGETID**: Unique identifier for the target object. If provided, the system will use this ID to match band cache files

### Catalog Format Example

The following is a simple example of a compliant catalog (structure shown in CSV format):

| TARGETID | RA        | DEC       |
|----------|-----------|-----------|
| 12345    | 150.12345 | 2.34567   |
| 12346    | 150.23456 | 2.45678   |
| 12347    | 150.34567 | 2.56789   |

### Catalog Limitations

- File size: No strict limit, but excessively large files may cause long processing times
- Row limit: Maximum support for 10,000 rows of data

## Band Caching Function

### Caching Principle

Band caching is a mechanism used to store processed image cropping results to avoid repeated processing of the same targets. The system saves processing results to band-classified directories, and cached files can be directly used when processing the same targets next time.

### Cache Directory Structure

```
/data/home/xiejh/Euclid_download/
├── VIS/            # Cache files for VIS band
├── NIR-Y/          # Cache files for NIR-Y band
├── NIR-J/          # Cache files for NIR-J band
├── NIR-H/          # Cache files for NIR-H band
├── DES-G/          # Cache files for DES-G band
├── DES-R/          # Cache files for DES-R band
├── DES-I/          # Cache files for DES-I band
├── DES-Z/          # Cache files for DES-Z band
└── ...             # Other bands
```

### Cache Retrieval Rules

The system retrieves cache files according to the following rules:
1. Match files containing the same ID in the filename based on TARGETID
2. Identify the corresponding file type based on file type identifiers
3. Determine the band through the directory where the cache file is located

### Cache Priority

1. First check if there are matching files in the band cache directory
2. If found, directly use the cache files to improve processing speed
3. If not found, perform normal image cropping processing
4. After processing is completed, automatically backup the results to the corresponding band cache directory

## Backend API Interfaces

### 1. File Upload

```
POST /api/upload_file
Content-Type: multipart/form-data

Parameters:
- catalog: FITS format catalog file
```

Response:
```json
{
  "success": true,
  "temp_id": "temporary_file_id",
  "filename": "uploaded_filename",
  "message": "File uploaded successfully"
}
```

### 2. Submit Task

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

Response:
```json
{
  "success": true,
  "task_id": "task_id",
  "message": "Task submitted"
}
```

### 3. Get Task Status

```
GET /api/task_status?task_id=task_id
```

Response:
```json
{
  "task_id": "task_id",
  "status": "completed", // queued, processing, completed, failed
  "progress": 100,
  "message": "Task processing completed",
  "result_url": "download_url"
}
```

## Common Issues and Troubleshooting

### File Upload Failure
- Ensure the uploaded file is in FITS format
- Check the file size, excessively large files may require longer time

### Task Processing Failure
- Check if the catalog format is correct, especially the RA and DEC columns
- Confirm that the selected instrument and band combination is valid
- Check server logs for detailed error information

### Cache File Mismatch
- Ensure the catalog contains the correct TARGETID column
- Check if the cache file naming conforms to the specification, should include TARGETID

## Performance Optimization Suggestions

1. For batch processing of a large number of targets, it is recommended to appropriately increase the number of parallel workers (n_workers)
2. Prioritize using the band caching function to avoid repeated processing
3. For frequently processed targets, ensure TARGETID is provided to improve cache hit rate
4. Check the status of existing cache files in the band cache directory before processing

## Technical Support

For any questions or suggestions, please contact the system administrator.

