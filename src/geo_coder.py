"""地理编码模块 - 逆地理编码及缓存管理"""
import os
import json
import logging
import sqlite3
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class GeoCodeCache:
    """逆地理编码结果缓存（支持 SQLite/JSON 可配置）"""

    CACHE_DIR = None  # 运行时设置
    CACHE_DB = None   # 运行时设置
    CACHE_JSON = None  # 运行时设置

    def __init__(self, cache_dir: str, cache_type: str = 'sqlite'):
        os.makedirs(cache_dir, exist_ok=True)
        GeoCodeCache.CACHE_DIR = cache_dir
        GeoCodeCache.CACHE_DB = os.path.join(cache_dir, 'cache.db')
        GeoCodeCache.CACHE_JSON = os.path.join(cache_dir, 'geocode_cache.json')

        self._use_sqlite = cache_type == 'sqlite'

        if self._use_sqlite:
            self._init_db()
            self._migrate_json_if_needed()
        else:
            self._cache = self._load_json_cache()

    # ==================== SQLite 实现 ====================
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.CACHE_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    lat REAL NOT NULL,
                    lng REAL NOT NULL,
                    place_name TEXT,
                    address TEXT,
                    administrative TEXT,
                    PRIMARY KEY (lat, lng)
                )
            ''')

    def _migrate_json_if_needed(self):
        """迁移旧 JSON 缓存数据到 SQLite"""
        if os.path.exists(self.CACHE_JSON):
            try:
                with open(self.CACHE_JSON, 'r', encoding='utf-8') as f:
                    old_cache = json.load(f)

                if not old_cache:
                    return

                with sqlite3.connect(self.CACHE_DB) as conn:
                    for key, value in old_cache.items():
                        lat_str, lng_str = key.split(',')
                        lat = float(lat_str)
                        lng = float(lng_str)
                        conn.execute('''
                            INSERT OR REPLACE INTO geocode_cache
                            (lat, lng, place_name, address, administrative)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            lat, lng,
                            value.get('place_name'),
                            value.get('address'),
                            json.dumps(value.get('administrative', {}), ensure_ascii=False)
                        ))

                os.rename(self.CACHE_JSON, self.CACHE_JSON + '.bak')
                logger.info(f"已迁移 {len(old_cache)} 条缓存数据到 SQLite")

            except Exception as e:
                logger.warning(f"迁移旧缓存失败: {e}")

    def _sqlite_get(self, lat: float, lng: float) -> Optional[Dict]:
        """SQLite 获取缓存"""
        lat_r = round(lat, 5)
        lng_r = round(lng, 5)

        with sqlite3.connect(self.CACHE_DB) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT place_name, address, administrative
                FROM geocode_cache
                WHERE lat = ? AND lng = ?
            ''', (lat_r, lng_r))
            row = cursor.fetchone()

            if row:
                result = {
                    'place_name': row['place_name'],
                    'address': row['address']
                }
                if row['administrative']:
                    result['administrative'] = json.loads(row['administrative'])
                return result
            return None

    def _sqlite_set(self, lat: float, lng: float, value: Dict):
        """SQLite 设置缓存"""
        lat_r = round(lat, 5)
        lng_r = round(lng, 5)

        with sqlite3.connect(self.CACHE_DB) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO geocode_cache
                (lat, lng, place_name, address, administrative)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                lat_r, lng_r,
                value.get('place_name'),
                value.get('address'),
                json.dumps(value.get('administrative', {}), ensure_ascii=False)
            ))

    # ==================== JSON 实现 ====================
    def _load_json_cache(self) -> Dict:
        """加载 JSON 缓存文件"""
        if os.path.exists(self.CACHE_JSON):
            try:
                with open(self.CACHE_JSON, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"缓存文件加载失败: {e}")
        return {}

    def _save_json_cache(self):
        """保存 JSON 缓存到文件"""
        try:
            with open(self.CACHE_JSON, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"缓存文件保存失败: {e}")

    def _json_get(self, lat: float, lng: float) -> Optional[Dict]:
        """JSON 获取缓存"""
        key = self._make_key(lat, lng)
        return self._cache.get(key)

    def _json_set(self, lat: float, lng: float, value: Dict):
        """JSON 设置缓存"""
        key = self._make_key(lat, lng)
        self._cache[key] = value
        self._save_json_cache()

    # ==================== 统一接口 ====================
    def _make_key(self, lat: float, lng: float) -> str:
        """生成缓存键（精度到小数点后5位，约1.1米）"""
        lat_r = round(lat, 5)
        lng_r = round(lng, 5)
        return f"{lat_r},{lng_r}"

    def get(self, lat: float, lng: float) -> Optional[Dict]:
        """获取缓存的地点信息"""
        if self._use_sqlite:
            return self._sqlite_get(lat, lng)
        else:
            return self._json_get(lat, lng)

    def set(self, lat: float, lng: float, value: Dict):
        """设置缓存的地点信息"""
        if self._use_sqlite:
            return self._sqlite_set(lat, lng, value)
        else:
            return self._json_set(lat, lng, value)


# 全局缓存实例
_geocode_cache = None


def get_geocode_cache(cache_dir: str = None, cache_type: str = 'sqlite') -> GeoCodeCache:
    """获取地理编码缓存实例"""
    global _geocode_cache
    if _geocode_cache is None:
        if cache_dir is None:
            raise ValueError("cache_dir is required on first call")
        _geocode_cache = GeoCodeCache(cache_dir, cache_type)
    return _geocode_cache


def get_location_by_coords(lat: float, lng: float) -> str:
    """根据坐标判断大致地理位置（用于境外地点或边境地区）

    Args:
        lat: 纬度
        lng: 经度

    Returns:
        str: 大致位置描述
    """
    # 判断是否在中国境内（主要区域）
    # 中国大致范围：纬度 18-54，经度 73-135
    if 18 <= lat <= 54 and 73 <= lng <= 135:
        # 进一步检查是否是边境/偏远地区（西藏/新疆/云南/四川边境）
        # 经度 < 80 或者在特定纬度范围内
        if lng < 80 or (24 <= lat <= 32 and lng <= 98):
            # 西藏/尼泊尔/印度边境地区
            if 24 <= lat <= 30 and 78 <= lng <= 98:
                return "西藏/尼泊尔边境地区"
            # 中缅边境
            elif 21 <= lat <= 26 and 97 <= lng <= 106:
                return "中缅边境地区"
            # 新疆/中亚边境
            elif 35 <= lat <= 45 and 74 <= lng <= 80:
                return "新疆/中亚边境地区"
        return None  # 在中国境内

    # 境外区域判断
    region = ""

    # 东亚/南亚
    if 26 <= lat <= 46 and 65 <= lng <= 105:
        if 27 <= lat <= 30 and 88 <= lng <= 98:  # 珠穆朗玛峰/喜马拉雅区域
            region = "珠穆朗玛峰区域（喜马拉雅山脉）"
        elif 26 <= lat <= 30 and 90 <= lng <= 98:
            region = "西藏边境地区"
        elif 20 <= lat <= 28 and 90 <= lng <= 110:
            region = "东南亚"
        elif lat > 35 and lng > 100:
            region = "蒙古"
        else:
            region = "中亚"

    # 南亚/尼泊尔/印度
    elif 6 <= lat <= 36 and 68 <= lng <= 100:
        if 26 <= lat <= 31 and 80 <= lng <= 90:
            region = "尼泊尔/喜马拉雅区域"
        elif lat < 30:
            region = "印度/巴基斯坦"
        else:
            region = "中亚"

    # 欧洲
    elif 35 <= lat <= 71 and -10 <= lng <= 40:
        region = "欧洲"

    # 北美
    elif 24 <= lat <= 72 and -170 <= lng <= -50:
        region = "北美洲"

    # 南美
    elif -55 <= lat <= 12 and -80 <= lng <= -34:
        region = "南美洲"

    # 非洲
    elif -35 <= lat <= 37 and -20 <= lng <= 52:
        region = "非洲"

    # 大洋洲
    elif -47 <= lat <= -10 and 110 <= lng <= 180:
        region = "大洋洲"

    # 日本/韩国
    elif 24 <= lat <= 46 and 119 <= lng <= 150:
        region = "日本/韩国"

    if region:
        return f"境外（{region}）"
    return "境外"


def batch_get_place_info(coords: List[Tuple[float, float]], amap_key: str) -> Dict:
    """批量调用高德逆地理编码 API

    Args:
        coords: [(lat, lng), ...] 坐标列表
        amap_key: 高德 API Key

    Returns:
        dict: {(lat, lng): result_dict, ...}
    """
    import requests

    if not coords:
        return {}

    # 批量请求最多 20 个坐标
    BATCH_SIZE = 20
    results = {}

    for i in range(0, len(coords), BATCH_SIZE):
        batch = coords[i:i + BATCH_SIZE]
        locations = "|".join([f"{lng},{lat}" for lat, lng in batch])

        try:
            url = "https://restapi.amap.com/v3/geocode/regeo"
            params = {
                "key": amap_key,
                "location": locations,
                "extensions": "all",
                "batch": "true"  # 启用批量模式
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            regeocodes = data.get("regeocodes", [])
            if isinstance(regeocodes, list) and len(regeocodes) == len(batch):
                for j, regeo in enumerate(regeocodes):
                    lat, lng = batch[j]
                    results[(lat, lng)] = parse_regeo_result(regeo, lat, lng)
            else:
                # 批量失败，回退到逐个请求
                logger.warning(f"批量请求返回数量不匹配，回退逐个请求")
                for lat, lng in batch:
                    results[(lat, lng)] = get_place_info_single(lat, lng, amap_key)
        except Exception as e:
            logger.error(f"批量请求失败: {e}")
            # 回退到逐个请求
            for lat, lng in batch:
                results[(lat, lng)] = get_place_info_single(lat, lng, amap_key)

    return results


def get_place_info_single(lat: float, lng: float, amap_key: str) -> Dict:
    """调用高德逆地理编码 API 获取单个坐标的地点信息（无缓存）

    Args:
        lat: 纬度
        lng: 经度
        amap_key: 高德 API Key

    Returns:
        dict: 包含 place_name 和 address
    """
    import requests

    try:
        url = "https://restapi.amap.com/v3/geocode/regeo"
        params = {
            "key": amap_key,
            "location": f"{lng},{lat}",
            "extensions": "all"
        }
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()

        if data.get("status") == "1" and data.get("regeocode"):
            regeo = data["regeocode"]
            return parse_regeo_result(regeo, lat, lng)
    except Exception as e:
        logger.error(f"逆地理编码失败: {e}")

    # API 失败时使用坐标推断
    location_hint = get_location_by_coords(lat, lng)
    if location_hint:
        return {"place_name": location_hint, "address": "", "administrative": {"province": "", "city": "", "district": ""}}

    return {"place_name": "未知地点", "address": "", "administrative": {"province": "", "city": "", "district": ""}}


def parse_regeo_result(regeo: Dict, lat: float, lng: float) -> Dict:
    """解析逆地理编码结果

    Args:
        regeo: 高德 API 返回的 regeocode 对象
        lat, lng: 原始坐标

    Returns:
        dict: 标准化的地点信息
    """
    address = regeo.get("formatted_address", "")
    address_component = regeo.get("addressComponent", {})
    province = address_component.get("province", "")
    city = address_component.get("city", "")
    district = address_component.get("district", "")
    township = address_component.get("township", "")

    # 优先使用 POI 名称
    place_name = ""
    pois_data = regeo.get("pois")
    pois = []
    if pois_data:
        if isinstance(pois_data, dict):
            pois = pois_data.get("poi", [])
        elif isinstance(pois_data, list):
            pois = pois_data

    if pois and isinstance(pois, list) and len(pois) > 0:
        poi = pois[0]
        if isinstance(poi, dict):
            place_name = poi.get("name", "")
            poi_address = poi.get("address", "")
            if poi_address and poi_address != "undefined":
                address = poi_address

    # 如果没有 POI，使用省市区
    if not place_name:
        parts = [p for p in [province, city, district, township] if p]
        place_name = "".join(parts) if parts else ""

    # 境外/边境地区使用坐标推断
    if not place_name or not address:
        location_hint = get_location_by_coords(lat, lng)
        if location_hint:
            return {"place_name": location_hint, "address": "", "administrative": {"province": "", "city": "", "district": ""}}

    # 清理空白
    if isinstance(place_name, str):
        place_name = place_name.strip()
    else:
        place_name = str(place_name) if place_name else ""

    if isinstance(address, str):
        address = address.strip()
    else:
        address = str(address) if address else ""

    return {
        "place_name": place_name,
        "address": address,
        "administrative": {
            "province": province,
            "city": city,
            "district": district
        }
    }
