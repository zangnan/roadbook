"""坐标转换模块 - WGS84 to GCJ02 (高德地图坐标)"""
import math


def wgs84_to_gcj02(lng, lat):
    """WGS84 (GPS原始坐标) 转 GCJ02 (高德/国测局坐标)

    Args:
        lng: WGS84 经度
        lat: WGS84 纬度

    Returns:
        tuple: (gcj_lng, gcj_lat) GCJ02 坐标
    """
    a = 6378245.0  # 长半轴
    ee = 0.00669342162296594323  # 扁率

    def transform(lat, lng):
        dlat = -100.0 + 2.0 * lng + 3.0 * lat + 2.0 * lat * lng + lng * lng * 0.00001 + lat * lat * lng * lng * 0.000000001
        dlng = 300.0 + lng + 2.0 * lat + lng * lat * 0.00001 + lng * lng * lng * 0.0000000001
        return dlat, dlng

    dlat, dlng = transform(lat - 35.0, lng - 105.0)
    radlat = lat / 180.0 * math.pi
    magic = 1 - ee * math.sin(radlat) ** 2
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lng + dlng, lat + dlat


def haversine_distance(lat1, lon1, lat2, lon2):
    """计算两点间距离（米）使用 Haversine 公式

    Args:
        lat1, lon1: 第一个点的纬度和经度
        lat2, lon2: 第二个点的纬度和经度

    Returns:
        float: 两点间距离（米）
    """
    R = 6371000  # 地球半径（米）

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
