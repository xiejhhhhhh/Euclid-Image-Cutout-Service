"""
Euclid数据裁剪工具 - 支持多仪器多波段批量裁剪

2025.10.21
xiejinhui22@mails.ucas.ac.cn
renhaoye@shao.ac.cn
主要功能:
1. 从catalog批量裁剪指定文件类型(BGSUB, CATALOG-PSF, FLAG, BGMOD, RMS)
2. 支持指定仪器和波段过滤
3. 支持矩形裁剪
4. 支持并行处理或单进程处理
5. 自动TILE ID查询

仪器和波段说明:
- instruments参数使用目录名: 'VIS', 'NISP', 'DECAM'
- bands参数使用文件名中的完整波段标识:
  * NISP: 'NIR-Y', 'NIR-J', 'NIR-H'
  * DECAM: 'DES-G', 'DES-R', 'DES-I', 'DES-Z'
  * VIS: 'VIS'
  * HSC: 'WISHES-G', 'WISHES-Z'
  * GPC: 'PANSTARRS-I'
  * MEGACAM: 'CFIS-U', 'CFIS-R

使用示例:
    catalog = Table.read('sources.fits')
    
    # 示例1: 裁剪VIS数据
    process_catalog(
        catalog=catalog,
        output_dir='output/',
        file_types=['BGSUB', 'CATALOG-PSF'],
        instruments=['VIS'],
        size=128,
        parallel=True,
        n_workers=8
    )
"""

from astropy.io import fits
from astropy.table import Table
from astropy.wcs import WCS
from astropy.nddata import Cutout2D
from astropy.coordinates import SkyCoord
import numpy as np
import os
import sys
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed, ThreadPoolExecutor
from typing import Union, Optional, Tuple, List, Dict
import warnings
warnings.filterwarnings('ignore', message='invalid value encountered in log10')


# ============================================================================
# 文件查找和TILE管理
# ============================================================================

def generate_tile_index(tile_catalog_root: str, output_file: str, 
                        catalog_pattern: str = 'EUC_MER_FINAL-CAT_TILE') -> Table:
    """生成TILE坐标索引
    
    参数:
        tile_catalog_root: TILE catalog文件的根目录
        output_file: 索引输出文件路径
        catalog_pattern: catalog文件名匹配模式
    """
    tile_info_list = []
    tile_dirs = [d for d in os.listdir(tile_catalog_root)
                 if os.path.isdir(os.path.join(tile_catalog_root, d))]
    
    for tile_id in tqdm(tile_dirs, desc="扫描TILE"):
        tile_path = os.path.join(tile_catalog_root, tile_id)
        try:
            catalog_files = [f for f in os.listdir(tile_path)
                           if catalog_pattern in f and f.endswith('.fits')]
            if not catalog_files:
                continue
            
            catalog_file = os.path.join(tile_path, catalog_files[0])
            with fits.open(catalog_file) as hdul:
                cat_table = Table(hdul[1].data)
                
                if 'RIGHT_ASCENSION' in cat_table.colnames and 'DECLINATION' in cat_table.colnames:
                    ra_col, dec_col = 'RIGHT_ASCENSION', 'DECLINATION'
                elif 'RA' in cat_table.colnames and 'DEC' in cat_table.colnames:
                    ra_col, dec_col = 'RA', 'DEC'
                else:
                    continue
                
                tile_info_list.append({
                    'TILE_ID': tile_id,
                    'RA_MIN': float(np.min(cat_table[ra_col])),
                    'RA_MAX': float(np.max(cat_table[ra_col])),
                    'DEC_MIN': float(np.min(cat_table[dec_col])),
                    'DEC_MAX': float(np.max(cat_table[dec_col])),
                    'RA_CENTER': float(np.mean(cat_table[ra_col])),
                    'DEC_CENTER': float(np.mean(cat_table[dec_col])),
                    'N_OBJECTS': len(cat_table)
                })
                
        except Exception as e:
            print(f"处理TILE {tile_id} 时出错: {e}")
            continue
    
    tile_index = Table(tile_info_list)
    tile_index.write(output_file, format='fits', overwrite=True)
    print(f"索引已保存: {output_file}, 共 {len(tile_index)} 个TILE")
    return tile_index


def query_tile_id(ra: float, dec: float, tile_index_file: str, 
                  tolerance: float = 0.01) -> Optional[str]:
    """根据坐标查询TILE ID"""
    try:
        tile_table = Table.read(tile_index_file)
        mask = (
            (tile_table['RA_MIN'] - tolerance <= ra) &
            (ra <= tile_table['RA_MAX'] + tolerance) &
            (tile_table['DEC_MIN'] - tolerance <= dec) &
            (dec <= tile_table['DEC_MAX'] + tolerance)
        )
        
        matched_tiles = tile_table[mask]
        
        if len(matched_tiles) == 0:
            return None
        elif len(matched_tiles) == 1:
            return str(matched_tiles['TILE_ID'][0])
        else:
            coord = SkyCoord(ra, dec, unit='deg')
            tile_centers = SkyCoord(matched_tiles['RA_CENTER'],
                                   matched_tiles['DEC_CENTER'], unit='deg')
            separations = coord.separation(tile_centers)
            nearest_idx = np.argmin(separations)
            return str(matched_tiles['TILE_ID'][nearest_idx])
            
    except Exception as e:
        print(f"查询TILE ID时出错: {e}")
        return None


def _get_file_pattern(file_type: str) -> str:
    """获取文件名匹配模式

    支持用户友好的文件类型名称映射到实际的文件命名模式：
    - SCI -> BGSUB (背景扣除后的科学图像)
    - WHT -> FLAG (权重/标志图)
    - RMS -> RMS (噪声图)
    """
    # 用户友好名称到实际文件模式的映射
    pattern_map = {
        'SCI': 'BGSUB-MOSAIC',      # 科学图像
        'WHT': 'MOSAIC',            # 权重图（使用FLAG文件）
        'BGSUB': 'BGSUB-MOSAIC',
        'BGMOD': 'BGMOD',
        'FLAG': 'MOSAIC',
        'RMS': 'MOSAIC',
        'CATALOG-PSF': 'CATALOG-PSF'
    }
    return pattern_map.get(file_type, file_type)


def _get_instrument_prefix_map() -> Dict[str, str]:
    """获取仪器目录名到文件名前缀的映射
    
    返回:
        dict: {目录名: 文件名前缀}
        例如: {'DECAM': 'DES', 'NISP': 'NIR', 'VIS': 'VIS'}
    """
    return {
        'DECAM': 'DES',
        'NISP': 'NIR',
        'VIS': 'VIS',
        'HSC': 'WISHES',
        'GPC': 'PANSTARRS',
        'MEGACAM': 'CFIS',
    }


def _parse_filename(filename: str, file_type: str) -> Optional[Tuple[str, str]]:
    """
    从文件名解析仪器和波段

    返回: (instrument, band) 或 None
    """
    try:
        notile = filename.split("_TILE")[0]

        # WHT映射到FLAG，需要使用FLAG的解析逻辑
        actual_file_type = file_type
        if file_type == 'WHT':
            actual_file_type = 'FLAG'

        if actual_file_type in ['FLAG', 'RMS']:
            inst_band = notile.split("EUC_MER_MOSAIC-")[-1].split(f"-{actual_file_type}")[0]
        else:
            pattern = _get_file_pattern(file_type)
            inst_band = notile.split(f"EUC_MER_{pattern}-")[-1]

        parts = inst_band.split('-')
        if len(parts) == 1:
            # 单通道仪器，如VIS
            return parts[0], parts[0]
        else:
            # 多波段仪器，如DES-G, NIR-Y
            instrument = parts[0]
            band = '-'.join(parts[1:])
            return instrument, band

    except Exception:
        return None


def find_files(tile_id: str, file_type: str, mer_root: str,
               instruments: Optional[List[str]] = None, bands: Optional[List[str]] = None) -> Dict:
    """
    查找指定TILE的文件
    
    参数:
        tile_id: TILE ID
        file_type: 文件类型 (BGSUB, CATALOG-PSF, FLAG, BGMOD, RMS)
        mer_root: MER数据根目录
        instruments: 仪器过滤列表（目录名，如NISP, DECAM, VIS），None表示所有仪器
        bands: 波段过滤列表（文件名中的波段，如NIR-Y, DES-G），None表示所有波段
        
    返回:
        dict: {'{instrument}_{band}': filepath}
        注意：返回的key使用目录名作为instrument
    """
    mer_dir = os.path.join(mer_root, str(tile_id))
    if not os.path.exists(mer_dir):
        return {}
    
    pattern = _get_file_pattern(file_type)
    instrument_prefix_map = _get_instrument_prefix_map()
    found_files = {}
    
    for instrument_dir in os.listdir(mer_dir):
        inst_path = os.path.join(mer_dir, instrument_dir)
        if not os.path.isdir(inst_path):
            continue
        
        # 如果指定了仪器过滤，检查目录名
        if instruments is not None and instrument_dir not in instruments:
            continue
        
        search_pattern = f'EUC_MER_{pattern}'
        fits_files = [f for f in os.listdir(inst_path)
                     if search_pattern in f and f.endswith('.fits')]

        # 过滤掉目录文件（如FINAL-CAT文件）
        filtered_files = []
        for fits_file in fits_files:
            # 跳过目录文件，这些文件不应该被当作图像文件处理
            if 'FINAL-CAT' in fits_file:
                continue

            # 根据file_type进行更精确的过滤
            # WHT -> FLAG文件（包含-FLAG）
            # RMS -> RMS文件（包含-RMS）
            # SCI -> BGSUB文件（包含BGSUB）
            if file_type == 'WHT':
                if '-FLAG' not in fits_file:
                    continue
            elif file_type == 'RMS':
                if '-RMS' not in fits_file:
                    continue
            elif file_type == 'SCI':
                if 'BGSUB' not in fits_file:
                    continue
            elif file_type == 'FLAG':
                if '-FLAG' not in fits_file:
                    continue
            elif file_type == 'BGSUB':
                if 'BGSUB' not in fits_file:
                    continue

            filtered_files.append(fits_file)

        fits_files = filtered_files
        
        for fits_file in fits_files:
            parsed = _parse_filename(fits_file, file_type)
            if parsed is None:
                continue
                
            file_instrument, file_band = parsed
            
            # 如果指定了波段过滤，检查文件名中的完整波段标识
            # 例如：bands=['NIR-Y', 'DES-G']
            if bands is not None:
                # 构建完整的波段标识（前缀-波段）
                full_band = f"{file_instrument}-{file_band}" if file_instrument != file_band else file_band
                if full_band not in bands:
                    continue
            
            # 使用目录名作为instrument，保持一致性
            key = f"{instrument_dir}_{file_instrument}-{file_band}" if file_instrument != file_band else f"{instrument_dir}_{file_band}"
            found_files[key] = os.path.join(inst_path, fits_file)
    
    return found_files


# ============================================================================
# 裁剪核心函数
# ============================================================================

def cutout_image(fits_path: str, ra: float, dec: float, size: Union[int, Tuple],
                 hdu_index: int = 0, mode: str = 'partial',
                 fill_value: float = 0) -> Dict:
    """
    裁剪FITS图像
    
    参数:
        size: 裁剪尺寸，整数表示正方形，元组(height, width)表示矩形
        hdu_index: HDU索引
        mode: 裁剪模式 ('partial', 'trim', 'strict')
        fill_value: 填充值
        
    返回:
        dict: {
            'success': bool,
            'data': ndarray,
            'wcs': WCS,
            'header': Header,
            'error': str,
            'contains_nan': bool
        }
    """
    result = {
        'success': False,
        'data': None,
        'wcs': None,
        'header': None,
        'error': None,
        'contains_nan': False
    }
    
    try:
        with fits.open(fits_path) as hdul:
            img_data = hdul[hdu_index].data
            img_header = hdul[hdu_index].header
            
            wcs = WCS(img_header)
            center = SkyCoord(ra, dec, unit='deg')
            cutout = Cutout2D(img_data, center, size, wcs=wcs,
                            mode=mode, fill_value=fill_value)
            
            result['success'] = True
            result['data'] = cutout.data
            result['wcs'] = cutout.wcs
            result['header'] = cutout.wcs.to_header()
            result['contains_nan'] = np.isnan(cutout.data).any()
            
    except Exception as e:
        result['error'] = str(e)
    
    return result


def cutout_psf(psf_fits_path: str, ra: float, dec: float) -> Dict:
    """
    裁剪PSF catalog，找到最近的PSF
    
    返回:
        dict: 与cutout_image相同的结构
    """
    result = {
        'success': False,
        'data': None,
        'wcs': None,
        'header': None,
        'error': None,
        'contains_nan': False
    }
    
    try:
        with fits.open(psf_fits_path) as hdul:
            img_data = hdul[1].data
            img_header = hdul[1].header
            psf_table = Table(hdul[2].data)
            stmpsize = img_header.get('STMPSIZE', 0)
            
            if stmpsize == 0:
                result['error'] = "PSF文件中没有STMPSIZE信息"
                return result
            
            target_coord = SkyCoord(ra, dec, unit='deg')
            psf_coords = SkyCoord(psf_table['RA'], psf_table['Dec'], unit='deg')
            separations = target_coord.separation(psf_coords)
            nearest_idx = np.argmin(separations)
            nearest_psf = psf_table[nearest_idx]
            
            psf_center_x = nearest_psf['x_center']
            psf_center_y = nearest_psf['y_center']
            
            half_size = stmpsize // 2
            x_min = max(0, int(psf_center_x - half_size) - 1)
            y_min = max(0, int(psf_center_y - half_size) - 1)
            
            if x_min + stmpsize > img_data.shape[1]:
                x_min = img_data.shape[1] - stmpsize
            if y_min + stmpsize > img_data.shape[0]:
                y_min = img_data.shape[0] - stmpsize
            
            if x_min < 0 or y_min < 0:
                result['error'] = "PSF裁剪区域超出图像边界"
                return result
            
            psf_cutout = img_data[y_min:y_min+stmpsize, x_min:x_min+stmpsize]
            
            if psf_cutout.size == 0:
                result['error'] = "PSF裁剪得到空数组"
                return result
            
            header = fits.Header()
            header['STMPSIZE'] = stmpsize
            header['PSF_RA'] = nearest_psf['RA']
            header['PSF_DEC'] = nearest_psf['Dec']
            if 'FWHM' in nearest_psf.colnames:
                header['PSF_FWHM'] = nearest_psf['FWHM']
            header['PSF_IDX'] = nearest_idx
            header['PSF_XCTR'] = psf_center_x
            header['PSF_YCTR'] = psf_center_y
            
            result['success'] = True
            result['data'] = psf_cutout
            result['wcs'] = None
            result['header'] = header
            result['contains_nan'] = np.isnan(psf_cutout).any()
            
    except Exception as e:
        result['error'] = str(e)
    
    return result


def cutout_tile(tile_id: str, ra: float, dec: float, size: Union[int, Tuple],
                file_type: str, mer_root: str,
                instruments: Optional[List[str]] = None, bands: Optional[List[str]] = None,
                skip_nan: bool = True) -> Dict:
    """
    从TILE裁剪指定文件类型的所有匹配波段
    
    参数:
        size: 裁剪尺寸，整数或(height, width)元组
        file_type: 文件类型
        skip_nan: 是否跳过包含NaN的结果
        
    返回:
        dict: {
            'success': bool,
            'cutouts': dict,  # {'{inst}_{band}': cutout_result}
            'error': str
        }
    """
    result = {
        'success': False,
        'cutouts': {},
        'error': None
    }
    
    try:
        files = find_files(tile_id, file_type, mer_root, instruments, bands)
        
        if not files:
            result['error'] = f"未找到TILE {tile_id} 的 {file_type} 文件"
            return result
        
        for key, filepath in files.items():
            # 处理星表文件和其他文件类型不同的key格式
            if file_type == 'CATALOG-PSF':
                # 对于星表文件，key可能没有标准的仪器-波段格式
                # 尝试解析，如果失败则使用默认值
                try:
                    instrument, band = key.split('_', 1)
                except ValueError:
                    # 如果无法解析，使用默认的仪器和波段标识
                    instrument = 'CATALOG'
                    band = 'PSF'
            else:
                # 对于图像文件，标准格式是{instrument}_{band}
                try:
                    instrument, band = key.split('_', 1)
                except ValueError:
                    print(f"警告: 无法解析文件key {key} 的仪器和波段信息")
                    continue
            
            if file_type == 'CATALOG-PSF':
                cutout_result = cutout_psf(filepath, ra, dec)
            else:
                cutout_result = cutout_image(filepath, ra, dec, size)
            
            if cutout_result['success']:
                if cutout_result['contains_nan'] and skip_nan:
                    continue
                
                cutout_result['instrument'] = instrument
                cutout_result['band'] = band
                result['cutouts'][key] = cutout_result
        
        if result['cutouts']:
            result['success'] = True
        else:
            result['error'] = "所有波段裁剪都失败或包含NaN"
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


# ============================================================================
# 保存函数
# ============================================================================

def save_cutouts(output_path: str, cutouts_result: Dict, obj_id: Optional[str] = None,
                 catalog_row: Optional[Table.Row] = None, overwrite: bool = True,
                 verbose: bool = False) -> bool:
    """
    保存裁剪结果到FITS文件
    
    参数:
        output_path: 输出文件路径
        cutouts_result: cutout_tile返回的结果
        obj_id: 对象ID，写入主HDU
        catalog_row: catalog行数据，作为表格HDU添加
        
    返回:
        bool: 是否成功保存
    """
    try:
        if not cutouts_result['success']:
            return False
        
        primary_hdu = fits.PrimaryHDU()
        if obj_id is not None:
            primary_hdu.header['OBJID'] = obj_id
        
        hdul = fits.HDUList([primary_hdu])
        hdu_index = 1
        
        for key, cutout_info in cutouts_result['cutouts'].items():
            cutout_hdu = fits.ImageHDU(data=cutout_info['data'])
            
            if cutout_info['wcs'] is not None:
                cutout_header = cutout_info['wcs'].to_header()
                for hkey in cutout_header:
                    cutout_hdu.header[hkey] = cutout_header[hkey]
            
            if cutout_info['header'] is not None:
                for hkey in cutout_info['header']:
                    if hkey not in cutout_hdu.header:
                        cutout_hdu.header[hkey] = cutout_info['header'][hkey]
            
            cutout_hdu.header['INSTRUME'] = cutout_info['instrument']
            cutout_hdu.header['BAND'] = cutout_info['band']
            primary_hdu.header[f'HDU{hdu_index}'] = key
            
            hdul.append(cutout_hdu)
            hdu_index += 1
        
        if catalog_row is not None:
            source_table = Table()
            for col_name in catalog_row.colnames:
                source_table[col_name] = [catalog_row[col_name]]
            table_hdu = fits.BinTableHDU(source_table)
            hdul.append(table_hdu)
            primary_hdu.header['SRCTABLE'] = len(hdul) - 1
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        hdul.writeto(output_path, overwrite=overwrite)
        
        return True
        
    except Exception as e:
        if verbose:
            print(f"保存FITS文件时出错: {e}")
        return False


# ============================================================================
# 批处理函数
# ============================================================================

def _process_single_source(source, source_index, output_dir, config):
    """处理单个源，执行裁剪操作并保存结果"""
    ra = source[config['ra_col']]
    dec = source[config['dec_col']]
    size = config['size']
    instruments = config.get('instruments', ['VIS'])
    file_types = config['file_types']
    bands = config.get('bands', None)
    target_id_col = config.get('target_id_col')
    current_target_id = config.get('current_target_id', source_index)
    
    # 获取TILE_ID
    tile_id = query_tile_id(ra, dec)
    
    # 使用文件缓存（如果提供）
    tile_files_cache = config.get('tile_files_cache', {})
    
    # 记录裁剪结果
    results = []
    
    # 对每个仪器和文件类型进行裁剪
    for instrument in instruments:
        for file_type in file_types:
            try:
                # 构建缓存键
                cache_key = (tile_id, instrument, file_type)
                
                # 查找对应的文件（使用缓存或重新查找）
                if cache_key not in tile_files_cache:
                    tile_files_cache[cache_key] = find_files(tile_id, instrument=instrument, file_type=file_type)
                files = tile_files_cache[cache_key]
                
                if not files:
                    raise FileNotFoundError(f"未找到TILE {tile_id}的{instrument}仪器{file_type}类型文件")
                
                # 根据文件类型执行不同的裁剪操作
                if file_type == 'PSF':
                    # PSF文件裁剪
                    cutout_result = cutout_psf(files, ra, dec)
                    if cutout_result:
                        results.append((instrument, file_type, None, cutout_result))
                else:
                    # 图像文件裁剪 - 处理所有匹配的波段文件
                    for file in files:
                        # 从文件名解析波段，修复解包错误
                        parsed = _parse_filename(file)
                        if parsed is not None:
                            file_instrument, band = parsed
                            # 使用从文件名解析出的仪器名称
                            if file_instrument != instrument:
                                print(f"警告: 文件 {file} 中的仪器 {file_instrument} 与预期 {instrument} 不匹配")
                        else:
                            # 如果解析失败，跳过此文件
                            print(f"警告: 无法解析文件 {file} 的仪器和波段信息")
                            continue
                            
                        cutout_result = cutout_image(file, ra, dec, size)
                        results.append((instrument, file_type, band, cutout_result))
            
            except Exception as e:
                print(f"处理目标{current_target_id}的{instrument}仪器{file_type}类型时出错: {e}")
                continue
    
    # 保存裁剪结果 - 按波段分组保存
    # 按 (instrument, file_type, band) 分组裁剪结果
    cutout_results_by_band = {}
    for instrument, file_type, band, cutout_data in results:
        if cutout_data['success']:
            band_key = f"{instrument}_{file_type}_{band}"
            if band_key not in cutout_results_by_band:
                cutout_results_by_band[band_key] = {
                    'success': True,
                    'cutouts': {},
                    'error': None
                }
            
            # 为每个波段创建单独的cutout条目
            cutout_results_by_band[band_key]['cutouts'][f"{instrument}_{band}"] = {
                'success': True,
                'data': cutout_data['data'],
                'wcs': cutout_data.get('wcs'),
                'header': cutout_data.get('header'),
                'instrument': instrument,
                'band': band,
                'contains_nan': cutout_data.get('contains_nan', False)
            }
    
    # 保存每个波段的裁剪结果到单独的文件
    for band_key, band_cutouts in cutout_results_by_band.items():
        try:
            instrument, file_type, band = band_key.split('_', 2)
            filename = f"{current_target_id}_{band}.fits"
            
            # 保存到输出目录
            output_path = os.path.join(output_dir, filename)
            
            if band_cutouts['cutouts']:
                # 转换为正确的cutout_tile格式
                cutout_result_for_save = {
                    'success': True,
                    'cutouts': band_cutouts['cutouts'],
                    'error': None
                }
                
                success = save_cutouts(
                    output_path=output_path,
                    cutouts_result=cutout_result_for_save,
                    obj_id=str(current_target_id)
                )
                
                if success:
                    print(f"已保存波段 {band}: {filename}")
                else:
                    print(f"保存波段 {band}失败: {filename}")
            else:
                print(f"波段 {band}没有有效的裁剪结果")
                
        except Exception as e:
            print(f"保存波段 {band}结果时出错: {e}")
            continue

def _process_single_source_parallel(args):
    """单个源的处理函数，用于并行处理"""
    try:
        (idx, row_dict, ra_col, dec_col, size_col, obj_id_col, file_types,
         output_dir, mer_root, instruments, bands,
         skip_nan, default_size, save_catalog_row, verbose) = args

        ra = row_dict[ra_col]
        dec = row_dict[dec_col]

        if size_col is not None and size_col in row_dict:
            size = row_dict[size_col]
            if isinstance(size, (list, tuple, np.ndarray)) and len(size) == 2:
                size = tuple(size)
        else:
            size = default_size

        # 确保obj_id是字符串类型，避免MaskedConstant导致的哈希错误
        if obj_id_col:
            raw_obj_id = row_dict[obj_id_col]
            # 检查是否为MaskedConstant类型或其他特殊类型
            if hasattr(raw_obj_id, 'mask'):  # MaskedConstant类型
                obj_id = f"ra_{ra:.6f}_dec_{dec:.6f}"  # 如果是掩码值，使用RA/Dec作为备用ID
            else:
                obj_id = str(raw_obj_id)  # 转换为字符串
        else:
            obj_id = f"ra_{ra:.6f}_dec_{dec:.6f}"  # 使用RA/Dec作为ID

        # 直接从row_dict中获取TILE_ID（已在process_catalog中预处理）
        # Note: all keys are lowercase now
        tile_id = row_dict['tile_id']
    except Exception as e:
        import traceback
        print(f"\n[ERROR] 解析参数时出错: {str(e)}", file=sys.stderr)
        print(f"row_dict keys: {list(row_dict.keys()) if isinstance(row_dict, dict) else 'NOT A DICT'}", file=sys.stderr)
        print(f"ra_col: {ra_col}, dec_col: {dec_col}, obj_id_col: {obj_id_col}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise
    
    # 如果TILE_ID为空字符串，说明无法匹配
    if not tile_id or tile_id == '':
        if verbose:
            print(f"[ERROR] obj_{idx} ({ra:.4f}, {dec:.4f}): 无法找到对应的TILE")
        return {'obj_id': obj_id, 'results': {ft: 'no_tile' for ft in file_types}}
    
    results = {}
    for file_type in file_types:
        try:
            cutout_result = cutout_tile(
                tile_id=str(tile_id),
                ra=ra,
                dec=dec,
                size=size,
                file_type=file_type,
                mer_root=mer_root,
                instruments=instruments,
                bands=bands,
                skip_nan=skip_nan
            )
            
            if cutout_result['success']:
                file_output_dir = os.path.join(output_dir, file_type)
                output_path = os.path.join(file_output_dir, f"{obj_id}.fits")

                # Convert dict back to Table Row for saving if needed
                save_row = None
                if save_catalog_row and file_type == file_types[0]:
                    # Create a single-row Table from the dict
                    from astropy.table import Table
                    temp_table = Table({k: [v] for k, v in row_dict.items()})
                    save_row = temp_table[0]

                success = save_cutouts(
                    output_path=output_path,
                    cutouts_result=cutout_result,
                    obj_id=obj_id,
                    catalog_row=save_row,
                    verbose=verbose
                )
                
                if success:
                    results[file_type] = 'success'
                else:
                    results[file_type] = 'save_failed'
                    if verbose:
                        print(f"[ERROR] {obj_id} {file_type}: 保存失败")
            else:
                error_msg = cutout_result.get('error', 'Unknown error')
                results[file_type] = f'cutout_failed: {error_msg}'
                # 只在非批量模式或明确需要详细输出时打印错误信息
                if verbose and len(results) == 1:
                    print(f"[ERROR] {obj_id} {file_type}: {error_msg}")
        
        except Exception as e:
            results[file_type] = f'error: {str(e)}'
            if verbose:
                print(f"[ERROR] {obj_id} {file_type}: {str(e)}")
    
    return {'obj_id': obj_id, 'results': results}


def _process_tile_group(tile_id, tile_sources, output_dir, config, original_indices):
    """处理一组属于同一TILE的源"""
    stats = {'success': 0, 'error': 0, 'count': len(tile_sources)}
    
    for i, (source, original_idx) in enumerate(zip(tile_sources, original_indices)):
        try:
            _process_single_source(source, original_idx, output_dir, config)
            stats['success'] += 1
        except Exception as e:
            print(f"处理TILE {tile_id}中的源{original_idx}失败: {e}")
            stats['error'] += 1
    
    return stats

def process_catalog_by_tile(catalog, output_dir, file_types, ra_col='RA', dec_col='DEC', size=100, 
                          instruments=None, bands=None, target_id_col=None, parallel=True, 
                          n_workers=4, verbose=False, task_id=None, tasks=None, tasks_lock=None):
    """
    按TILE_ID分配进程处理星表，每个TARGETID裁剪一个图像fits文件
    
    参数:
        catalog: 星表数据，可以是astropy Table或pandas DataFrame
        output_dir: 输出目录（直接输出到持久化目录）
        file_types: 要处理的文件类型列表，如['IMG', 'WEIGHT', 'PSF']
        ra_col: RA列名
        dec_col: DEC列名
        size: 裁剪大小（像素）
        instruments: 要处理的仪器列表，如['VIS', 'NIR']
        bands: 要处理的波段列表
        target_id_col: TARGETID列名
        parallel: 是否并行处理
        n_workers: 并行工作进程数
        verbose: 是否显示详细信息
        task_id: 任务ID（用于进度更新）
        tasks: 任务字典（用于进度更新）
        tasks_lock: 任务锁（用于进度更新）
    
    返回:
        处理统计信息字典
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 初始化统计信息 - 按文件类型分别统计
    stats = {}
    for file_type in file_types:
        stats[file_type] = {'success': 0, 'failed': 0, 'total': len(catalog)}
    
    # 为所有源获取TILE_ID
    ra_list = catalog[ra_col].tolist()
    dec_list = catalog[dec_col].tolist()
    tile_ids = []
    target_ids = []
    
    # 收集TARGET_IDs
    if target_id_col and target_id_col in catalog.colnames:
        target_ids = catalog[target_id_col].tolist()
    else:
        target_ids = list(range(len(catalog)))
    
    # 使用query_tile_id批量获取TILE_ID
    for ra, dec in zip(ra_list, dec_list):
        try:
            tile_id = query_tile_id(ra, dec)
            tile_ids.append(tile_id)
        except Exception as e:
            print(f"获取坐标({ra}, {dec})的TILE_ID失败: {e}")
            tile_ids.append(None)
    
    # 按TILE_ID分组
    tile_groups = {}
    for idx, (tile_id, target_id) in enumerate(zip(tile_ids, target_ids)):
        if tile_id not in tile_groups:
            tile_groups[tile_id] = []
        tile_groups[tile_id].append((idx, target_id))
    
    print(f"共找到 {len(tile_groups)} 个不同的TILE_ID")
    
    # 配置参数
    config = {
        'file_types': file_types,
        'ra_col': ra_col,
        'dec_col': dec_col,
        'size': size,
        'instruments': instruments,
        'bands': bands,
        'target_id_col': target_id_col
    }
    
    # 初始化进度
    processed_count = 0
    total_sources = len(catalog)
    
    # 并行处理 - 每个TILE_ID一个进程
    if parallel:
        with ProcessPoolExecutor(max_workers=min(n_workers, len(tile_groups))) as executor:
            # 提交任务
            future_to_tile = {}
            for tile_id, source_info in tile_groups.items():
                if tile_id is not None:
                    # 提取此TILE的源索引和目标ID
                    source_indices = [idx for idx, _ in source_info]
                    tile_sources = catalog[source_indices]
                    # 传递目标ID列表
                    tile_target_ids = [target_id for _, target_id in source_info]
                    
                    future = executor.submit(
                        _process_tile_group_with_targets, 
                        tile_id, tile_sources, output_dir, config, source_indices, tile_target_ids
                    )
                    future_to_tile[future] = tile_id
                else:
                    # 处理没有TILE_ID的源（单独处理）
                    for idx, target_id in source_info:
                        source = catalog[idx]
                        try:
                            # 使用_target_id重命名文件
                            config['current_target_id'] = target_id
                            _process_single_source(source, idx, output_dir, config)
                            for file_type in file_types:
                                stats[file_type]['success'] += 1
                            
                            # 更新进度
                            processed_count += 1
                            if task_id and tasks and tasks_lock:
                                progress = int(30 + (processed_count / total_sources) * 60)  # 30%-90%
                                with tasks_lock:
                                    tasks[task_id]['progress'] = min(progress, 90)
                                    tasks[task_id]['message'] = f"正在处理: {processed_count}/{total_sources}"
                        except Exception as e:
                            print(f"处理目标{target_id}失败: {e}")
                            for file_type in file_types:
                                stats[file_type]['failed'] += 1
            
            # 收集结果
            for future in as_completed(future_to_tile):
                tile_id = future_to_tile[future]
                try:
                    result = future.result()
                    # 更新统计信息
                    for file_type in file_types:
                        if file_type in result:
                            stats[file_type]['success'] += result[file_type].get('success', 0)
                            stats[file_type]['failed'] += result[file_type].get('failed', 0)
                    
                    # 更新进度
                    processed_count += result.get('count', 0)
                    if task_id and tasks and tasks_lock:
                        progress = int(30 + (processed_count / total_sources) * 60)
                        with tasks_lock:
                            tasks[task_id]['progress'] = min(progress, 90)
                            tasks[task_id]['message'] = f"正在处理: {processed_count}/{total_sources}"
                            
                    print(f"TILE {tile_id} 处理完成: 成功{sum(r['success'] for r in result.values())}个源")
                except Exception as e:
                    print(f"处理TILE {tile_id}失败: {e}")
                    # 标记此TILE中的所有源为失败
                    failed_count = len(tile_groups[tile_id])
                    for file_type in file_types:
                        stats[file_type]['failed'] += failed_count
    else:
        # 串行处理
        for tile_id, source_info in tile_groups.items():
            if tile_id is not None:
                try:
                    source_indices = [idx for idx, _ in source_info]
                    tile_sources = catalog[source_indices]
                    tile_target_ids = [target_id for _, target_id in source_info]
                    
                    result = _process_tile_group_with_targets(
                        tile_id, tile_sources, output_dir, config, source_indices, tile_target_ids
                    )
                    
                    # 更新统计信息
                    for file_type in file_types:
                        if file_type in result:
                            stats[file_type]['success'] += result[file_type].get('success', 0)
                            stats[file_type]['failed'] += result[file_type].get('failed', 0)
                    
                    # 更新进度
                    processed_count += result.get('count', 0)
                    if task_id and tasks and tasks_lock:
                        progress = int(30 + (processed_count / total_sources) * 60)
                        with tasks_lock:
                            tasks[task_id]['progress'] = min(progress, 90)
                            tasks[task_id]['message'] = f"正在处理: {processed_count}/{total_sources}"
                except Exception as e:
                    print(f"处理TILE {tile_id}失败: {e}")
            else:
                for idx, target_id in source_info:
                    source = catalog[idx]
                    try:
                        config['current_target_id'] = target_id
                        _process_single_source(source, idx, output_dir, config)
                        for file_type in file_types:
                            stats[file_type]['success'] += 1
                    except Exception as e:
                        print(f"处理目标{target_id}失败: {e}")
                        for file_type in file_types:
                            stats[file_type]['failed'] += 1
    
    # 打印最终统计信息
    for file_type in file_types:
        success = stats[file_type]['success']
        failed = stats[file_type]['failed']
        total = stats[file_type]['total']
        print(f"{file_type}处理统计: 成功{success}, 失败{failed}, 总计{total}")
    
    return stats

def _process_tile_group_with_targets(tile_id, tile_sources, output_dir, config, original_indices, target_ids):
    """处理一组属于同一TILE的源，并使用TARGET_ID命名文件"""
    # 初始化统计信息
    stats = {}
    for file_type in config['file_types']:
        stats[file_type] = {'success': 0, 'failed': 0}
    stats['count'] = len(tile_sources)
    
    # 预先加载该TILE的文件信息，减少重复查找
    tile_files_cache = {}
    
    # 处理每个源
    for i, (source, original_idx, target_id) in enumerate(zip(tile_sources, original_indices, target_ids)):
        try:
            # 设置当前目标ID
            config['current_target_id'] = target_id
            config['tile_files_cache'] = tile_files_cache  # 传递文件缓存
            
            # 处理单个源
            _process_single_source(source, original_idx, output_dir, config)
            
            # 更新所有文件类型的成功计数
            for file_type in config['file_types']:
                stats[file_type]['success'] += 1
                
        except Exception as e:
            print(f"处理TILE {tile_id}中的目标{target_id}失败: {e}")
            # 更新所有文件类型的失败计数
            for file_type in config['file_types']:
                stats[file_type]['failed'] += 1
    
    return stats

def process_catalog(catalog: Table, output_dir: str, file_types: List[str],
                    ra_col: str = 'RA', dec_col: str = 'DEC',
                    size_col: Optional[str] = None, obj_id_col: Optional[str] = None,
                    size: Union[int, Tuple] = 128,
                    tile_index_file: str = 'data/EuclidQ1_tile_coordinates.fits',
                    mer_root: str = '/data/astrodata/mirror/102042-Euclid-Q1/MER',
                    instruments: Optional[List[str]] = None, bands: Optional[List[str]] = None,
                    skip_nan: bool = True, save_catalog_row: bool = True,
                    parallel: bool = False, n_workers: int = 4, verbose: bool = False) -> Dict:
    """
    批量处理catalog
    
    参数:
        catalog: 输入catalog表
        output_dir: 输出根目录
        file_types: 要裁剪的文件类型列表
        ra_col: RA列名
        dec_col: DEC列名
        size_col: size列名，如果为None则使用统一size
        obj_id_col: 对象ID列名
        size: 统一裁剪尺寸，整数或(height, width)元组
        tile_index_file: TILE索引文件路径
        mer_root: MER数据根目录
        instruments: 仪器过滤列表
        bands: 波段过滤列表
        skip_nan: 是否跳过包含NaN的结果
        save_catalog_row: 是否保存catalog行到第一个文件类型
        parallel: 是否并行处理
        n_workers: 并行worker数量
        verbose: 是否输出详细错误信息
        
    返回:
        dict: 统计信息 {file_type: {'success': int, 'failed': int, 'errors': list}}
    """
    
    if ra_col not in catalog.colnames or dec_col not in catalog.colnames:
        raise ValueError(f"catalog必须包含指定的RA/DEC列: {ra_col}, {dec_col}")
    
    if obj_id_col is None:
        if 'OBJECT_ID' in catalog.colnames:
            obj_id_col = 'OBJECT_ID'
        elif 'ID' in catalog.colnames:
            obj_id_col = 'ID'
    
    # 批量获取TILE_ID（如果catalog中没有）
    catalog_with_tile = catalog.copy()
    if 'TILE_ID' not in catalog.colnames:
        if verbose:
            print("正在批量查询TILE_ID...")
        tile_ids = []
        for row in tqdm(catalog, desc="查询TILE_ID", disable=not verbose):
            tile_id = query_tile_id(row[ra_col], row[dec_col], tile_index_file)
            tile_ids.append(tile_id if tile_id is not None else '')
        catalog_with_tile['TILE_ID'] = tile_ids
        
        # 统计无TILE_ID的源
        n_no_tile = sum(1 for tid in tile_ids if tid == '')
        if n_no_tile > 0 and verbose:
            print(f"警告: {n_no_tile}/{len(catalog)} 个源无法匹配到TILE_ID")
    
    stats = {ft: {'success': 0, 'failed': 0, 'errors': []} for ft in file_types}
    
    # Convert rows to dicts for better serialization in multiprocessing
    # Also normalize column names to lowercase for case-insensitive access
    args_list = [
        (idx, {col.lower(): row[col] for col in row.colnames},
         ra_col.lower(), dec_col.lower(),
         size_col.lower() if size_col else None,
         obj_id_col.lower() if obj_id_col else None,
         file_types,
         output_dir, mer_root, instruments, bands,
         skip_nan, size, save_catalog_row, verbose)
        for idx, row in enumerate(catalog_with_tile)
    ]
    
    if parallel:
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(_process_single_source_parallel, args): args 
                      for args in args_list}
            
            pbar = tqdm(total=len(futures), desc="批量裁剪", position=0, leave=True)
            
            for future in as_completed(futures):
                try:
                    result_dict = future.result()
                    obj_id = result_dict['obj_id']
                    results = result_dict['results']
                    
                    for file_type, status in results.items():
                        if status == 'success':
                            stats[file_type]['success'] += 1
                        else:
                            stats[file_type]['failed'] += 1
                            if verbose and len(stats[file_type]['errors']) < 10:
                                stats[file_type]['errors'].append(f"{obj_id}: {status}")
                except Exception as e:
                    if verbose:
                        import traceback
                        print(f"\n[CRITICAL ERROR] 处理任务时出错: {str(e)}", file=sys.stderr)
                        print(f"详细错误信息:", file=sys.stderr)
                        traceback.print_exc(file=sys.stderr)
                    for file_type in file_types:
                        stats[file_type]['failed'] += 1
                
                # 更新进度条描述显示当前统计
                total_success = sum(s['success'] for s in stats.values())
                total_failed = sum(s['failed'] for s in stats.values())
                pbar.set_postfix({'成功': total_success, '失败': total_failed}, refresh=True)
                pbar.update(1)
            
            pbar.close()
    else:
        pbar = tqdm(args_list, desc="批量裁剪", position=0, leave=True)
        for args in pbar:
            try:
                result_dict = _process_single_source_parallel(args)
                obj_id = result_dict['obj_id']
                results = result_dict['results']
                
                for file_type, status in results.items():
                    if status == 'success':
                        stats[file_type]['success'] += 1
                    else:
                        stats[file_type]['failed'] += 1
                        if verbose and len(stats[file_type]['errors']) < 10:
                            stats[file_type]['errors'].append(f"{obj_id}: {status}")
            except Exception as e:
                if verbose:
                    print(f"\n[CRITICAL ERROR] 处理任务时出错: {str(e)}", file=sys.stderr)
                for file_type in file_types:
                    stats[file_type]['failed'] += 1
            
            # 更新进度条描述显示当前统计
            total_success = sum(s['success'] for s in stats.values())
            total_failed = sum(s['failed'] for s in stats.values())
            pbar.set_postfix({'成功': total_success, '失败': total_failed}, refresh=True)
    
    print("\n" + "="*60)
    print("处理统计:")
    print("="*60)
    for file_type, stat in stats.items():
        print(f"{file_type}:")
        print(f"  成功: {stat['success']}")
        print(f"  失败: {stat['failed']}")
        if stat['errors'] and verbose:
            print(f"  前{len(stat['errors'])}个错误:")
            for err in stat['errors']:
                print(f"    - {err}")
    print("="*60)
    
    return stats


# ============================================================================
# 主程序示例
# ============================================================================

if __name__ == "__main__":
    # 生成TILE索引
    # print("生成TILE坐标索引...")
    # tile_index = generate_tile_index(
    #     tile_catalog_root='/data/astrodata/mirror/102042-Euclid-Q1/catalogs/MER_FINAL_CATALOG/',
    #     output_file='/data1/public/Euclid/Q1/code/tile_coordinates.fits'
    # )
    # print(f"索引生成完成，共 {len(tile_index)} 个TILE\n")
    
    # 批量裁剪示例
    catalog = Table.read('/data/home/xiejh/Q1_match_DR1.fits')
    # stats = process_catalog(
    #     catalog=catalog,
    #     output_dir='/data1/public/Euclid/Q1/cutouts/astro_IR/overlap_DR1/Euclid',
    #     file_types=['CATALOG-PSF','BGSUB', 'RMS'],
    #     ra_col='RA_2',
    #     dec_col='DEC_2',
    #     size=128,  # 或 size=(128, 256) 用于矩形
    #     instruments=['VIS'],
    #     parallel=True,
    #     n_workers=64
    # )
    catalog = catalog[:10]
    stats = process_catalog(
        catalog=catalog,
        output_dir='/data/home/xiejh/Euclid_cutout/',
        file_types=['CATALOG-PSF','BGSUB', 'RMS'],
        ra_col='RA_2',
        dec_col='DEC_2',
        size=64,  # 或 size=(128, 256) 用于矩形
        instruments=['NISP'],
        bands=["NIR-Y"],
        parallel=True,
        n_workers=64
    )