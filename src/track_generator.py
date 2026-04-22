"""轨迹生成模块 - 照片轨迹处理和HTML生成"""
import os
import json
import uuid
import base64
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)


def filter_nearby_points(points: List[Dict], distance_threshold: int = 1000, time_threshold: int = 7200) -> List[Dict]:
    """过滤相近坐标，合并重复点

    Args:
        points: 轨迹点列表（已按时间排序）
        distance_threshold: 距离阈值（米），默认1000米（1公里）
        time_threshold: 时间阈值（秒），默认2小时

    Returns:
        list: 过滤后的轨迹点
    """
    from coord_converter import haversine_distance

    if not points:
        return []

    filtered = []
    current_group = [points[0]]

    for i in range(1, len(points)):
        prev = current_group[-1]
        curr = points[i]

        # 计算距离
        dist = haversine_distance(
            prev['latitude'], prev['longitude'],
            curr['latitude'], curr['longitude']
        )

        # 计算时间差
        time_diff = 0
        if prev['timestamp'] and curr['timestamp']:
            try:
                t1 = datetime.fromisoformat(prev['timestamp'])
                t2 = datetime.fromisoformat(curr['timestamp'])
                time_diff = abs((t2 - t1).total_seconds())
            except:
                time_diff = 999999

        # 距离<阈值 且 时间差<阈值 → 归为同一组
        if dist < distance_threshold and time_diff < time_threshold:
            current_group.append(curr)
        else:
            # 保存当前组（取第一个点的坐标，保留所有照片）
            merged = current_group[0].copy()
            merged['photo_count'] = len(current_group)
            # 保存所有照片到 photo 数组
            merged['photo_group'] = current_group[:]
            filtered.append(merged)
            current_group = [curr]

    # 处理最后一组
    if current_group:
        merged = current_group[0].copy()
        merged['photo_count'] = len(current_group)
        # 保存所有照片到 photo 数组
        merged['photo_group'] = current_group[:]
        filtered.append(merged)

    return filtered


def segment_points_by_day(points: List[Dict], day_gap_hours: int = 4) -> List[Dict]:
    """根据时间间隔将轨迹分段（识别第1段/第2段/...）

    Args:
        points: 轨迹点列表（已按时间排序）
        day_gap_hours: 超过多少小时不连续则认为新的一段（默认4小时）

    Returns:
        list: 添加了 day_segment 字段的轨迹点列表
    """
    if not points:
        return points

    day_segment = 1
    last_time = None

    for i, point in enumerate(points):
        # 获取第一张照片的时间作为基准
        photo = point.get('photo_group', [point])
        if photo and photo[0].get('timestamp'):
            try:
                current_time = datetime.fromisoformat(photo[0]['timestamp'])
            except:
                current_time = None
        else:
            current_time = None

        if current_time and last_time:
            time_diff = (current_time - last_time).total_seconds()
            if time_diff > day_gap_hours * 3600:
                day_segment += 1
                logger.info(f"检测到第 {day_segment} 段（间隔 {time_diff/3600:.1f} 小时）")

        point['day_segment'] = day_segment
        last_time = current_time

    # 统计每天的点数量
    day_counts = {}
    for p in points:
        day = p.get('day_segment', 1)
        day_counts[day] = day_counts.get(day, 0) + 1

    logger.info(f"轨迹分段完成: {day_segment} 段, {day_counts}")
    return points


def process_single_photo(image_path: str, filename: str, thumbnail_folder: str, ext: str, supported_formats: set):
    """处理单张照片（供并行调用）

    Returns:
        dict: 包含 has_gps 字段的结果，有 GPS 时包含轨迹点数据，无 GPS 时包含基本信息
    """
    from exif_reader import read_gps_from_image, get_photo_timestamp
    from coord_converter import wgs84_to_gcj02
    from thumbnail import save_thumbnail, save_original

    # 读取 GPS 信息
    gps_data = read_gps_from_image(image_path)

    # 获取拍摄时间
    timestamp = get_photo_timestamp(image_path)

    # 生成 UUID
    photo_uuid = str(uuid.uuid4())

    # 生成缩略图和原图
    thumbnail_filename = f"{photo_uuid}.jpg"
    thumbnail_path = os.path.join(thumbnail_folder, thumbnail_filename)
    saved_path = save_thumbnail(image_path, thumbnail_path)
    thumbnail_rel_path = f"thumbnail/{photo_uuid}.jpg" if saved_path else ''

    original_filename = f"{photo_uuid}_orig.jpg"
    original_path = os.path.join(thumbnail_folder, original_filename)
    saved_original = save_original(image_path, original_path)
    original_rel_path = f"thumbnail/{original_filename}" if saved_original else ''

    # 判断是否有 GPS
    if not gps_data:
        logger.warning(f"跳过无 GPS 信息: {filename}")
        return {
            'has_gps': False,
            'point': {
                'uuid': photo_uuid,
                'latitude': None,
                'longitude': None,
                'altitude': None,
                'timestamp': timestamp,
                'filename': filename,
                'thumbnail_path': thumbnail_rel_path,
                'original_path': original_rel_path,
                'original_lng': None,
                'original_lat': None,
                'place_name': '',
                'address': ''
            }
        }

    # WGS84 -> GCJ02 坐标转换
    gcj_lng, gcj_lat = wgs84_to_gcj02(gps_data['longitude'], gps_data['latitude'])

    point = {
        'uuid': photo_uuid,
        'latitude': gcj_lat,
        'longitude': gcj_lng,
        'altitude': gps_data.get('altitude'),
        'timestamp': timestamp,
        'filename': filename,
        'thumbnail_path': thumbnail_rel_path,
        'original_path': original_rel_path,
        'original_lng': gps_data['longitude'],
        'original_lat': gps_data['latitude'],
        'place_name': '',
        'address': ''
    }

    logger.info(f"处理: {filename} -> ({gcj_lat:.6f}, {gcj_lng:.6f})")
    return {
        'has_gps': True,
        'point': point
    }


def collect_photo_points(photo_folder: str, output_folder: str, supported_formats: set) -> Tuple[List[Dict], List[Dict]]:
    """遍历文件夹收集所有照片轨迹点（并行处理）

    Args:
        photo_folder: 照片文件夹路径
        output_folder: 输出文件夹路径（用于保存缩略图）
        supported_formats: 支持的图片格式集合

    Returns:
        tuple: (points, unknown_points) - 有 GPS 的轨迹点列表和无 GPS 的照片列表
    """
    if not os.path.exists(photo_folder):
        logger.error(f"照片文件夹不存在: {photo_folder}")
        return [], []

    # 创建缩略图保存目录
    thumbnail_folder = os.path.join(output_folder, 'thumbnail')
    os.makedirs(thumbnail_folder, exist_ok=True)

    # 收集所有照片文件
    photo_files = []
    for filename in os.listdir(photo_folder):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in supported_formats:
            continue
        image_path = os.path.join(photo_folder, filename)
        photo_files.append((image_path, filename, ext))

    total_photos = len(photo_files)
    logger.info(f"找到 {total_photos} 个照片文件")

    # 并行处理照片
    points = []  # 有 GPS 的点
    unknown_points = []  # 无 GPS 的照片

    if photo_files:
        processed_count = 0
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(process_single_photo, image_path, filename, thumbnail_folder, ext, supported_formats): (image_path, filename)
                for image_path, filename, ext in photo_files
            }

            for future in as_completed(futures):
                image_path, filename = futures[future]
                try:
                    result = future.result()
                    processed_count += 1
                    if result:
                        has_gps = result.get('has_gps', False)
                        point = result.get('point')

                        if has_gps and point:
                            points.append(point)
                        elif point:
                            unknown_points.append(point)
                    # 每处理 10 张或最后一张时显示进度
                    if processed_count % 10 == 0 or processed_count == len(photo_files):
                        percent = processed_count * 100 // len(photo_files)
                        logger.info(f"处理进度: {processed_count}/{len(photo_files)} ({percent}%)")
                except Exception as e:
                    logger.error(f"处理失败 {filename}: {e}")

    # 按拍摄时间排序
    points.sort(key=lambda x: x['timestamp'] or '')
    unknown_points.sort(key=lambda x: x['timestamp'] or '')

    logger.info(f"照片处理完成，共 {len(points)} 个有效轨迹点, {len(unknown_points)} 个无 GPS 照片")
    return points, unknown_points


def resolve_place_names(points: List[Dict], amap_key: str, cache) -> List[Dict]:
    """批量解析轨迹点的地点名称

    Args:
        points: 轨迹点列表
        amap_key: 高德 API Key
        cache: 地理编码缓存实例

    Returns:
        list: 添加了地点信息的轨迹点列表
    """
    from geo_coder import batch_get_place_info, get_place_info_single

    # 使用 Set 去重，只解析唯一的坐标
    unique_coords = {}
    for point in points:
        # 使用 round 确保精度一致
        lat = round(point['latitude'], 5)
        lng = round(point['longitude'], 5)
        key = f"{lat},{lng}"
        if key not in unique_coords:
            unique_coords[key] = point

    unique_points = list(unique_coords.values())
    total_unique = len(unique_points)
    logger.info(f"开始解析 {total_unique} 个唯一坐标的地点信息...")

    cache_hit_count = 0
    need_api_coords = []  # 需要调用 API 的坐标
    checked_count = 0

    # 第一步：检查缓存，分离需要 API 的坐标
    for i, point in enumerate(unique_points):
        cached = cache.get(point['latitude'], point['longitude'])
        if cached:
            cache_hit_count += 1
            point['place_name'] = cached['place_name']
            point['address'] = cached['address']
            point['administrative'] = cached.get('administrative', {})
        else:
            need_api_coords.append((point['latitude'], point['longitude']))

        checked_count += 1
        # 每 20 个坐标或最后时显示缓存检查进度
        if checked_count % 20 == 0 or checked_count == total_unique:
            percent = checked_count * 100 // total_unique
            logger.info(f"进度: 缓存检查 {checked_count}/{total_unique} 个坐标 ({percent}%)")

    # 第二步：批量调用 API
    api_call_count = 0
    if need_api_coords:
        total_api = len(need_api_coords)
        logger.info(f"缓存未命中 {total_api} 个坐标，批量请求 API...")

        # 分批显示 API 请求进度
        api_processed = 0
        results = batch_get_place_info(need_api_coords, amap_key)
        api_call_count = len(results)
        api_processed = total_api
        percent = 100
        logger.info(f"进度: API 请求 {api_processed}/{total_api} 个坐标 ({percent}%)")

        # 保存到缓存并更新 point
        for point in unique_points:
            lat, lng = point['latitude'], point['longitude']
            if (lat, lng) in results:
                result = results[(lat, lng)]
                cache.set(lat, lng, result)
                point['place_name'] = result['place_name']
                point['address'] = result['address']
                point['administrative'] = result.get('administrative', {})

    logger.info(f"地点解析完成: API调用 {api_call_count} 次, 缓存命中 {cache_hit_count} 次")

    # 更新所有点的地点信息
    for point in points:
        # 使用和解析时相同的精度来匹配
        lat = round(point['latitude'], 5)
        lng = round(point['longitude'], 5)
        key = f"{lat},{lng}"
        if key in unique_coords:
            point['place_name'] = unique_coords[key].get('place_name', '')
            point['address'] = unique_coords[key].get('address', '')
            point['administrative'] = unique_coords[key].get('administrative', {})

    return points


def render_html_template(points: List[Dict], output_path: str, templates_dir: str, static_dir: str, amap_web_ak: str):
    """渲染 HTML 模板生成输出文件

    Args:
        points: 轨迹点列表
        output_path: 输出 HTML 路径
        templates_dir: 模板目录路径
        static_dir: 静态文件目录路径
        amap_web_ak: 高德地图 Web AK
    """
    if not os.path.exists(templates_dir):
        logger.error(f"模板目录不存在: {templates_dir}")
        return

    try:
        # 创建 Jinja2 环境
        env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )

        # 加载模板
        template = env.get_template('map_template.html')

        # 计算静态资源基础路径（output/{testX}/ 目录需回退两级到 travellingMap 根目录）
        static_base = '../../'

# 渲染模板
        html_content = template.render(
            amap_ak=amap_web_ak,
            static_base=static_base,
            track_points=points,
            single_html=False
        )

        # 写入输出文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"轨迹文件已生成: {output_path}")
        logger.info(f"共 {len(points)} 个轨迹点")

    except Exception as e:
        logger.error(f"模板渲染失败: {e}")
        raise


def load_css_inline(static_dir: str) -> str:
    """读取 CSS 文件内容

    Returns:
        str: CSS 文件内容（common.css + map.css）
    """
    css_files = ['common.css', 'map.css']
    css_contents = []
    for css_file in css_files:
        css_path = os.path.join(static_dir, css_file)
        try:
            with open(css_path, 'r', encoding='utf-8') as f:
                css_contents.append(f.read())
        except Exception as e:
            logger.error(f"读取 CSS 文件失败: {e}")
    return '\n'.join(css_contents)


def convert_car_icon_to_base64(static_dir: str) -> str:
    """转换小车图标为 Base64 Data URL

    Returns:
        str: Base64 Data URL 格式的小车图标
    """
    car_path = os.path.join(static_dir, 'assets', 'car.png')
    try:
        with open(car_path, 'rb') as f:
            img_data = f.read()
        b64_data = base64.b64encode(img_data).decode('utf-8')
        return f"data:image/png;base64,{b64_data}"
    except Exception as e:
        logger.error(f"转换小车图标失败: {e}")
        return ""


def convert_dir_marker_to_base64(static_dir: str) -> str:
    """转换 dir-marker.png 为 Base64 Data URL

    Returns:
        str: Base64 Data URL 格式的图标
    """
    marker_path = os.path.join(static_dir, 'assets', 'dir-marker.png')
    try:
        with open(marker_path, 'rb') as f:
            img_data = f.read()
        b64_data = base64.b64encode(img_data).decode('utf-8')
        return f"data:image/png;base64,{b64_data}"
    except Exception as e:
        logger.error(f"转换 dir-marker 图标失败: {e}")
        return ""


def convert_images_to_base64(points: List[Dict], output_folder: str) -> Tuple[List[Dict], List[Dict]]:
    """将所有图片转换为 Base64 Data URL

    Args:
        points: 轨迹点列表
        output_folder: 输出文件夹路径

    Returns:
        tuple: (original_points_with_base64, converted_points_with_base64)
    """
    # 转换 originalPoints 数据中的图片
    original_points = []
    for p in points:
        # 构建原始图片的绝对路径
        orig_path = p.get('original_path', '')
        if orig_path:
            abs_path = os.path.join(output_folder, orig_path)
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, 'rb') as f:
                        img_data = f.read()
                    b64_data = base64.b64encode(img_data).decode('utf-8')
                    orig_path = f"data:image/jpeg;base64,{b64_data}"
                except Exception as e:
                    logger.warning(f"转换原图失败 {abs_path}: {e}")

        thumb_path = p.get('thumbnail_path', '')
        if thumb_path:
            abs_path = os.path.join(output_folder, thumb_path)
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, 'rb') as f:
                        img_data = f.read()
                    b64_data = base64.b64encode(img_data).decode('utf-8')
                    thumb_path = f"data:image/jpeg;base64,{b64_data}"
                except Exception as e:
                    logger.warning(f"转换缩略图失败 {abs_path}: {e}")

        original_points.append({
            'uuid': p.get('uuid', ''),
            'latitude': p.get('latitude'),
            'longitude': p.get('longitude'),
            'altitude': p.get('altitude'),
            'timestamp': p.get('timestamp', ''),
            'filename': p.get('filename', ''),
            'thumbnail_path': thumb_path,
            'original_path': orig_path
        })

    # 转换 convertedPoints 数据中的图片
    converted_points = []
    for p in points:
        photo_group = p.get('photo_group', [p])
        converted_photos = []

        for photo in photo_group:
            orig_path = photo.get('original_path', '')
            if orig_path:
                abs_path = os.path.join(output_folder, orig_path)
                if os.path.exists(abs_path):
                    try:
                        with open(abs_path, 'rb') as f:
                            img_data = f.read()
                        b64_data = base64.b64encode(img_data).decode('utf-8')
                        orig_path = f"data:image/jpeg;base64,{b64_data}"
                    except Exception as e:
                        logger.warning(f"转换原图失败 {abs_path}: {e}")

            thumb_path = photo.get('thumbnail_path', '')
            if thumb_path:
                abs_path = os.path.join(output_folder, thumb_path)
                if os.path.exists(abs_path):
                    try:
                        with open(abs_path, 'rb') as f:
                            img_data = f.read()
                        b64_data = base64.b64encode(img_data).decode('utf-8')
                        thumb_path = f"data:image/jpeg;base64,{b64_data}"
                    except Exception as e:
                        logger.warning(f"转换缩略图失败 {abs_path}: {e}")

            converted_photos.append({
                'uuid': photo.get('uuid', ''),
                'latitude': photo.get('latitude'),
                'longitude': photo.get('longitude'),
                'altitude': photo.get('altitude'),
                'timestamp': photo.get('timestamp', ''),
                'filename': photo.get('filename', ''),
                'thumbnail_path': thumb_path,
                'original_path': orig_path
            })

        converted_points.append({
            'latitude_tran': p.get('latitude'),
            'longitude_tran': p.get('longitude'),
            'place_name': p.get('place_name', ''),
            'address': p.get('address', ''),
            'administrative': p.get('administrative', {}),
            'day_segment': p.get('day_segment', 1),
            'photo_count': p.get('photo_count', 1),
            'photo': converted_photos
        })

    return original_points, converted_points


def render_html_template_single(points: List[Dict], unknown_points: List[Dict], output_folder: str, output_path: str, templates_dir: str, static_dir: str, amap_web_ak: str):
    """渲染单一 HTML 文件（所有资源内联）

    Args:
        points: 轨迹点列表
        unknown_points: 无 GPS 的照片列表
        output_folder: 输出文件夹路径
        output_path: 输出 HTML 路径
        templates_dir: 模板目录路径
        static_dir: 静态文件目录路径
        amap_web_ak: 高德地图 Web AK
    """
    if not os.path.exists(templates_dir):
        logger.error(f"模板目录不存在: {templates_dir}")
        return

    try:
        # 加载 CSS
        css_content = load_css_inline(static_dir)

        # 转换小车图标和 dir-marker 图标
        car_icon_base64 = convert_car_icon_to_base64(static_dir)
        dir_marker_base64 = convert_dir_marker_to_base64(static_dir)

        # 转换所有图片为 Base64
        original_points, converted_points = convert_images_to_base64(points, output_folder)

        # 创建 Jinja2 环境
        env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )

        # 加载模板
        template = env.get_template('map_template.html')

        # 渲染模板（单一文件模式）
        html_content = template.render(
            amap_ak=amap_web_ak,
            static_base='',  # 单一文件模式不需要 base path
            track_points=points,
            single_html=True,
            css_content=css_content,
            car_icon_base64=car_icon_base64,
            dir_marker_base64=dir_marker_base64,
            original_points_json=json.dumps(original_points, ensure_ascii=False),
            converted_points_json=json.dumps(converted_points, ensure_ascii=False),
            unknown_points_json=json.dumps(unknown_points, ensure_ascii=False)
        )

        # 写入输出文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"单一 HTML 文件已生成: {output_path}")
        logger.info(f"共 {len(points)} 个轨迹点")

    except Exception as e:
        logger.error(f"单一文件模式渲染失败: {e}")
        raise


def generate_original_json(points: List[Dict], output_folder: str, unknown_points: List[Dict] = None) -> str:
    """生成 data_original.json 和 data_original_unknown.json

    Args:
        points: 轨迹点列表（已解析地点信息）
        output_folder: 输出文件夹路径
        unknown_points: 无 GPS 的照片列表

    Returns:
        str: 输出文件路径
    """
    # 排除没有 latitude、longitude 的数据
    valid_points = [p for p in points if p.get('latitude') and p.get('longitude')]

    # 构建输出数据（包含 place_name、address、administrative 等地点信息）
    original_data = []
    for p in valid_points:
        data = {
            'uuid': p.get('uuid', ''),
            'latitude': p['latitude'],
            'longitude': p['longitude'],
            'altitude': p.get('altitude'),
            'timestamp': p.get('timestamp', ''),
            'filename': p.get('filename', ''),
            'thumbnail_path': p.get('thumbnail_path', ''),
            'original_path': p.get('original_path', ''),
            'place_name': p.get('place_name', ''),
            'address': p.get('address', ''),
            'administrative': p.get('administrative', {})
        }
        original_data.append(data)

    output_path = os.path.join(output_folder, 'data_original.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(original_data, f, ensure_ascii=False, indent=2)

    logger.info(f"原始数据已生成: {output_path} ({len(original_data)} 条)")

    # 生成无 GPS 照片的 JSON 文件
    if unknown_points:
        unknown_data = []
        for p in unknown_points:
            data = {
                'uuid': p.get('uuid', ''),
                'latitude': p.get('latitude'),
                'longitude': p.get('longitude'),
                'altitude': p.get('altitude'),
                'timestamp': p.get('timestamp', ''),
                'filename': p.get('filename', ''),
                'thumbnail_path': p.get('thumbnail_path', ''),
                'original_path': p.get('original_path', ''),
                'place_name': '',
                'address': '',
                'administrative': {}
            }
            unknown_data.append(data)

        unknown_output_path = os.path.join(output_folder, 'data_original_unknown.json')
        with open(unknown_output_path, 'w', encoding='utf-8') as f:
            json.dump(unknown_data, f, ensure_ascii=False, indent=2)

        logger.info(f"无 GPS 照片数据已生成: {unknown_output_path} ({len(unknown_data)} 条)")

    return output_path


def generate_converted_json(points: List[Dict], output_folder: str) -> str:
    """生成 data_converted.json（数据治理后）

    Args:
        points: 轨迹点列表（已合并相近坐标）
        output_folder: 输出文件夹路径

    Returns:
        str: 输出文件路径
    """
    converted_data = []

    for p in points:
        # 使用 photo_group（如果存在）获取所有照片，否则使用单张照片
        photo_group = p.get('photo_group', [p])

        item = {
            'latitude_tran': p['latitude'],
            'longitude_tran': p['longitude'],
            'place_name': p.get('place_name', ''),
            'address': p.get('address', ''),
            'administrative': p.get('administrative', {}),
            'day_segment': p.get('day_segment', 1),
            'photo_count': p.get('photo_count', 1),
            'photo': [
                {
                    'uuid': photo.get('uuid', ''),
                    'latitude': photo['latitude'],
                    'longitude': photo['longitude'],
                    'altitude': photo.get('altitude'),
                    'timestamp': photo.get('timestamp', ''),
                    'filename': photo.get('filename', ''),
                    'thumbnail_path': photo.get('thumbnail_path', ''),
                    'original_path': photo.get('original_path', '')
                }
                for photo in photo_group
            ]
        }
        converted_data.append(item)

    output_path = os.path.join(output_folder, 'data_converted.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, ensure_ascii=False, indent=2)

    logger.info(f"治理数据已生成: {output_path} ({len(converted_data)} 条)")
    return output_path


# ========== 时间轴生成函数 ==========
def get_date_from_timestamp(ts: str) -> str:
    """从时间戳提取日期部分（YYYY-MM-DD）"""
    if not ts:
        return ''
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime('%Y-%m-%d')
    except:
        return ''


def format_timestamp(ts: str) -> str:
    """格式化时间戳为可读格式"""
    if not ts:
        return ''
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return ts


def format_date(ts: str) -> str:
    """格式化日期"""
    if not ts:
        return ''
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime('%Y年%m月%d日')
    except:
        return ts


def convert_image_references(points: List[Dict], output_folder: str) -> List[Dict]:
    """处理图片引用，返回相对于 output 文件夹的路径"""
    rel_base = './'

    converted_points = []

    for p in points:
        # 兼容 photo_group（完整流程）和 photo（JSON 文件）两种字段名
        photo_group = p.get('photo_group') or p.get('photo', [])
        converted_photos = []

        for photo in photo_group:
            thumb_path = photo.get('thumbnail_path', '')
            if thumb_path:
                thumb_path = rel_base + thumb_path

            orig_path = photo.get('original_path', '')
            if orig_path:
                orig_path = rel_base + orig_path

            converted_photos.append({
                'uuid': photo.get('uuid', ''),
                'timestamp': photo.get('timestamp', ''),
                'filename': photo.get('filename', ''),
                'thumbnail_path': thumb_path,
                'original_path': orig_path,
                'altitude': photo.get('altitude'),
                'latitude': photo.get('latitude'),
                'longitude': photo.get('longitude')
            })

        converted_points.append({
            'latitude_tran': p.get('latitude_tran') or p.get('latitude'),
            'longitude_tran': p.get('longitude_tran') or p.get('longitude'),
            'place_name': p.get('place_name', ''),
            'address': p.get('address', ''),
            'administrative': p.get('administrative', {}),
            'day_segment': p.get('day_segment', 1),
            'photo_count': p.get('photo_count', 1),
            'photo': converted_photos
        })

    return converted_points


def group_by_day_and_place(points: List[Dict]) -> Dict:
    """按实际日期和地点双重分组数据"""
    from collections import defaultdict

    day_groups = {}

    for p in points:
        photos = p.get('photo_group') or p.get('photo') or []
        if not photos:
            continue

        date_key = get_date_from_timestamp(photos[0].get('timestamp', ''))
        if not date_key:
            continue

        place_name = p.get('place_name', '未知地点')

        if date_key not in day_groups:
            day_groups[date_key] = {
                'date': '',
                'date_key': date_key,
                'places': defaultdict(lambda: {
                    'start_time': '',
                    'end_time': '',
                    'photo_count': 0,
                    'photos': []
                })
            }

        if not day_groups[date_key]['date']:
            day_groups[date_key]['date'] = format_date(photos[0].get('timestamp', ''))

        place_data = day_groups[date_key]['places'][place_name]

        if photos:
            first_ts = photos[0].get('timestamp', '')
            last_ts = photos[-1].get('timestamp', '')

            if not place_data['start_time'] or (first_ts and first_ts < place_data['start_time']):
                place_data['start_time'] = format_timestamp(first_ts)
            if not place_data['end_time'] or (last_ts and last_ts > place_data['end_time']):
                place_data['end_time'] = format_timestamp(last_ts)

            place_data['photos'].extend(photos)
            place_data['photo_count'] = len(place_data['photos'])

    result = {}
    for date_key in sorted(day_groups.keys()):
        day_data = day_groups[date_key]
        sorted_places = dict(sorted(day_data['places'].items(),
                                    key=lambda x: x[1]['photos'][0].get('timestamp', '') if x[1]['photos'] else ''))

        result[date_key] = {
            'date': day_data['date'],
            'date_key': date_key,
            'places': sorted_places,
            'total_photos': sum(p['photo_count'] for p in sorted_places.values())
        }

    return result


def calculate_total_distance(points: List[Dict]) -> float:
    """计算轨迹总里程（公里）"""
    from coord_converter import haversine_distance

    total = 0.0
    sorted_points = sorted(points, key=lambda p: (p.get('photo_group') or p.get('photo') or [{}])[0].get('timestamp', '') if (p.get('photo_group') or p.get('photo')) else '')
    for i in range(len(sorted_points) - 1):
        p1 = sorted_points[i]
        p2 = sorted_points[i + 1]
        lat1 = p1.get('latitude_tran') or p1.get('latitude')
        lon1 = p1.get('longitude_tran') or p1.get('longitude')
        lat2 = p2.get('latitude_tran') or p2.get('latitude')
        lon2 = p2.get('longitude_tran') or p2.get('longitude')
        if all([lat1, lon1, lat2, lon2]):
            # coord_converter.haversine_distance 返回米，需要转换为公里
            total += haversine_distance(lat1, lon1, lat2, lon2) / 1000
    return total


def calculate_altitude_range(points: List[Dict]) -> Tuple[Optional[float], Optional[float], str]:
    """计算海拔范围，返回 (最低, 最高, 单位)"""
    altitudes = []
    for p in points:
        for photo in (p.get('photo_group') or p.get('photo') or []):
            alt = photo.get('altitude')
            if alt is not None and alt > 0:
                altitudes.append(alt)

    if not altitudes:
        return None, None, 'm'

    return min(altitudes), max(altitudes), 'm'


def calculate_time_range(day_groups: Dict) -> Tuple[str, str]:
    """计算时间范围，返回格式化的起始日期和结束日期"""
    import re

    if not day_groups:
        return '', ''

    sorted_dates = sorted(day_groups.keys())
    start_date = day_groups[sorted_dates[0]]['date']
    end_date = day_groups[sorted_dates[-1]]['date']

    def extract_date_str(date_str):
        if not date_str:
            return ''
        match = re.search(r'(\d+)年(\d+)月(\d+)日', date_str)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        return date_str

    return extract_date_str(start_date), extract_date_str(end_date)


def render_timeline_template(converted_points: List[Dict], output_folder: str, output_path: str, templates_dir: str, static_dir: str):
    """渲染时间轴 HTML 模板"""
    if not os.path.exists(templates_dir):
        logger.error(f"模板目录不存在: {templates_dir}")
        return

    try:
        logger.info("正在处理图片引用...")
        converted_points = convert_image_references(converted_points, output_folder)

        day_groups = group_by_day_and_place(converted_points)

        total_photos = sum(day['total_photos'] for day in day_groups.values())

        total_distance = calculate_total_distance(converted_points)
        if total_distance >= 1:
            total_distance_str = f"{round(total_distance)} km"
        else:
            total_distance_str = f"{round(total_distance * 1000)} m"

        min_alt, max_alt, _ = calculate_altitude_range(converted_points)
        if min_alt is not None and max_alt is not None:
            altitude_range_str = f"{min_alt:.0f} ~ {max_alt:.0f} m"
        else:
            altitude_range_str = "未知"

        start_date, end_date = calculate_time_range(day_groups)
        if start_date and end_date:
            time_range_str = f"{start_date} ~ {end_date}"
        else:
            time_range_str = "未知"

        env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )

        env.filters['format_timestamp'] = format_timestamp
        env.filters['format_date'] = format_date

        template = env.get_template('timeline_template.html')

        # 计算静态资源基础路径（output/{testX}/ 目录需回退两级到 travellingMap 根目录）
        static_base = '../../'

        html_content = template.render(
            day_groups=day_groups,
            total_days=len(day_groups),
            total_photos=total_photos,
            total_distance=total_distance_str,
            altitude_range=altitude_range_str,
            time_range=time_range_str,
            static_base=static_base
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"时间轴页面已生成: {output_path}")
        logger.info(f"共 {len(day_groups)} 天, {total_photos} 张照片")

    except Exception as e:
        logger.error(f"时间轴模板渲染失败: {e}")
        raise
