"""EXIF GPS 信息读取模块"""
import exifread
from datetime import datetime


def read_gps_from_image(image_path):
    """读取单张照片的 GPS 信息

    Args:
        image_path: 照片文件路径

    Returns:
        dict: 包含 latitude, longitude, altitude 或 None
    """
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)

        # 尝试读取 GPS 信息
        gps_lat = tags.get('GPS GPSLatitude')
        gps_lat_ref = tags.get('GPS GPSLatitudeRef')
        gps_lng = tags.get('GPS GPSLongitude')
        gps_lng_ref = tags.get('GPS GPSLongitudeRef')
        gps_alt = tags.get('GPS GPSAltitude')

        if not all([gps_lat, gps_lat_ref, gps_lng, gps_lng_ref]):
            return None

        latitude = gps_to_decimal(gps_lat, gps_lat_ref)
        longitude = gps_to_decimal(gps_lng, gps_lng_ref)

        altitude = None
        if gps_alt:
            altitude = parse_fraction(str(gps_alt))

        return {
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude
        }
    except Exception as e:
        print(f"读取 GPS 信息失败 {image_path}: {e}")
        return None


def gps_to_decimal(gps_data, ref):
    """将度分秒格式转为十进制

    Args:
        gps_data: exifread GPS 坐标对象
        ref: N/S 或 E/W 标识

    Returns:
        float: 十进制经纬度
    """
    # 解析度分秒格式 [n, n, n]
    gps_str = str(gps_data)
    gps_str = gps_str.strip('[]')
    parts = [p.strip() for p in gps_str.split(',')]

    degrees = parse_fraction(parts[0])
    minutes = parse_fraction(parts[1])
    seconds = parse_fraction(parts[2])

    decimal = degrees + minutes / 60 + seconds / 3600

    # 根据参考方向确定正负
    ref_str = str(ref).strip()
    if ref_str in ['S', 'W']:
        decimal = -decimal

    return decimal


def parse_fraction(value):
    """解析分数或整数

    Args:
        value: 字符串如 "40/1" 或 "30"

    Returns:
        float: 解析后的数值
    """
    value = value.strip()
    if '/' in value:
        num, den = value.split('/')
        return float(num) / float(den)
    return float(value)


def get_photo_timestamp(image_path):
    """获取照片拍摄时间

    Args:
        image_path: 照片文件路径

    Returns:
        str: ISO 格式时间字符串
    """
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)

        # 尝试多种时间标签
        for tag_name in ['EXIF DateTimeOriginal', 'GPS GPSDate', 'Image DateTime']:
            date_str = tags.get(tag_name)
            if date_str:
                # 格式: "2024:03:15 10:30:00"
                dt_str = str(date_str)
                dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                return dt.isoformat()

        return None
    except Exception as e:
        print(f"读取时间信息失败 {image_path}: {e}")
        return None
