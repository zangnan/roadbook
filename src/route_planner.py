"""路径规划模块 - 高德路径规划 API 调用"""
import hashlib
import json
import logging
import os
import sqlite3
import time
import requests
from typing import Dict, List, Optional

from config import (
    APP_DIR,
    CACHE_TYPE,
    DRIVING_STRATEGY_PLANS,
    AMAP_DRIVING_STRATEGY_PARAMS,
    ROUTE_DEDUP_DISTANCE_THRESHOLD,
    ROUTE_DEDUP_TIME_THRESHOLD
)

logger = logging.getLogger(__name__)

# 高德 API 基础地址
AMAP_DIRECTION_URL = "https://restapi.amap.com/v3/direction"
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode"
AMAP_PLACE_URL = "https://restapi.amap.com/v3/place"


class RouteCache:
    """路径规划结果缓存（inputtips + 路径规划）"""

    CACHE_DIR = os.path.join(APP_DIR, 'cache')
    CACHE_DB = os.path.join(CACHE_DIR, 'route_cache.db')

    # 缓存有效期（秒）
    INPUTTIPS_TTL = 30 * 24 * 3600  # 30天
    ROUTE_TTL = 7 * 24 * 3600       # 7天

    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self._use_sqlite = CACHE_TYPE == 'sqlite'
        self._init_db()

    def _init_db(self):
        """初始化缓存数据库"""
        with sqlite3.connect(self.CACHE_DB) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS route_cache (
                    cache_key TEXT PRIMARY KEY,
                    cache_type TEXT NOT NULL,
                    cache_value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_expires ON route_cache(expires_at)
            ''')

    def _is_expired(self, expires_at: float) -> bool:
        """检查缓存是否过期"""
        return time.time() > expires_at

    def _make_inputtips_key(self, keywords: str) -> str:
        """生成 inputtips 缓存键"""
        return f"inputtips:{keywords}"

    def _make_route_key(self, from_lng: float, from_lat: float,
                        to_lng: float, to_lat: float, strategy: str,
                        strategy_param: str = None) -> str:
        """生成路径规划缓存键"""
        # 坐标精度到小数点后5位（约1.1米）
        key = f"route:{round(from_lng, 5)},{round(from_lat, 5)}_{round(to_lng, 5)},{round(to_lat, 5)}_{strategy}"
        if strategy_param:
            key += f"_{strategy_param}"
        return key

    def get_inputtips(self, keywords: str) -> Optional[Dict]:
        """获取 inputtips 缓存"""
        key = self._make_inputtips_key(keywords)
        try:
            with sqlite3.connect(self.CACHE_DB) as conn:
                cursor = conn.execute(
                    'SELECT cache_value, expires_at FROM route_cache WHERE cache_key = ?',
                    (key,)
                )
                row = cursor.fetchone()
                if row:
                    if self._is_expired(row[1]):
                        conn.execute('DELETE FROM route_cache WHERE cache_key = ?', (key,))
                        return None
                    return json.loads(row[0])
        except Exception as e:
            logger.warning(f"读取 inputtips 缓存失败: {e}")
        return None

    def set_inputtips(self, keywords: str, value: Dict):
        """设置 inputtips 缓存"""
        key = self._make_inputtips_key(keywords)
        now = time.time()
        try:
            with sqlite3.connect(self.CACHE_DB) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO route_cache (cache_key, cache_type, cache_value, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (key, 'inputtips', json.dumps(value, ensure_ascii=False), now, now + self.INPUTTIPS_TTL))
        except Exception as e:
            logger.warning(f"写入 inputtips 缓存失败: {e}")

    def get_route(self, from_lng: float, from_lat: float,
                  to_lng: float, to_lat: float, strategy: str,
                  strategy_param: str = None) -> Optional[Dict]:
        """获取路径规划缓存"""
        key = self._make_route_key(from_lng, from_lat, to_lng, to_lat, strategy, strategy_param)
        try:
            with sqlite3.connect(self.CACHE_DB) as conn:
                cursor = conn.execute(
                    'SELECT cache_value, expires_at FROM route_cache WHERE cache_key = ?',
                    (key,)
                )
                row = cursor.fetchone()
                if row:
                    if self._is_expired(row[1]):
                        conn.execute('DELETE FROM route_cache WHERE cache_key = ?', (key,))
                        return None
                    return json.loads(row[0])
        except Exception as e:
            logger.warning(f"读取 route 缓存失败: {e}")
        return None

    def set_route(self, from_lng: float, from_lat: float,
                  to_lng: float, to_lat: float, strategy: str,
                  value: Dict, strategy_param: str = None):
        """设置路径规划缓存"""
        key = self._make_route_key(from_lng, from_lat, to_lng, to_lat, strategy, strategy_param)
        now = time.time()
        try:
            with sqlite3.connect(self.CACHE_DB) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO route_cache (cache_key, cache_type, cache_value, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (key, 'route', json.dumps(value, ensure_ascii=False), now, now + self.ROUTE_TTL))
        except Exception as e:
            logger.warning(f"写入 route 缓存失败: {e}")


class RoutePlanner:
    """高德路径规划服务"""

    # 驾车/骑行支持途经点，步行不支持
    WAYPOINT_STRATEGIES = {"driving", "riding"}

    # 默认驾车策略
    DEFAULT_DRIVING_PLAN = "recommended"

    # 骑行子策略选项
    RIDING_STRATEGIES = {
        "0": "推荐路线",
        "1": "躲避拥堵"
    }

    def __init__(self, amap_key: str):
        self.amap_key = amap_key
        self._cache = RouteCache()

    def geocode(self, address: str) -> Dict:
        """地理编码：地址转坐标（使用 /v3/geocode/geo 接口）

        Args:
            address: 地址/地点名称

        Returns:
            {"status": "success", "name": str, "lng": float, "lat": float}
            {"status": "error", "error": str}
        """
        try:
            url = f"{AMAP_GEOCODE_URL}/geo"
            params = {
                "key": self.amap_key,
                "address": address,
                "output": "json"
            }
            resp = requests.get(url, params=params, timeout=5)
            data = resp.json()
            logger.info(f"地理编码响应: {data}")

            if data.get("status") == "1" and data.get("count", "0") != "0" and data.get("geocodes"):
                location = data["geocodes"][0].get("location", "")
                if location:
                    lng, lat = location.split(",")
                    province = data["geocodes"][0].get("province", "")
                    city = data["geocodes"][0].get("city", "")
                    return {
                        "status": "success",
                        "name": f"{province}{city}{address}",
                        "lng": float(lng),
                        "lat": float(lat)
                    }

            return {"status": "error", "error": data.get("info", "未找到该地址")}

        except Exception as e:
            logger.error(f"地理编码失败: {e}")
            return {"status": "error", "error": str(e)}

    def inputtips(self, keywords: str) -> Dict:
        """输入提示：高德 v3/place/text 地点搜索

        Args:
            keywords: 关键字

        Returns:
            {"status": "1", "tips": [{"name": str, "location": "lng,lat", "address": str, "district": str}, ...]}
        """
        # 先查缓存
        cached = self._cache.get_inputtips(keywords)
        if cached:
            logger.info(f"inputtips 缓存命中: {keywords}")
            return cached

        try:
            import urllib.parse
            url = f"{AMAP_PLACE_URL}/text"
            params = {
                "key": self.amap_key,
                "keywords": keywords,
                "output": "json",
                "pageSize": 10
            }
            # 手动构建 URL 并编码
            encoded_params = urllib.parse.urlencode(params)
            full_url = f"{url}?{encoded_params}"
            logger.info(f"inputtips full_url: {full_url[:100]}...")

            resp = requests.get(full_url, timeout=5)
            logger.info(f"inputtips response status: {resp.status_code}")
            logger.info(f"inputtips response text: {resp.text[:200]}")

            data = resp.json()
            logger.info(f"inputtips response data: status={data.get('status')}, count={data.get('count')}")

            if data.get("status") == "1" and data.get("pois"):
                tips = []
                for poi in data.get("pois", []):
                    location = poi.get("location", "")
                    if location:
                        tips.append({
                            "name": poi.get("name", ""),
                            "location": location,
                            "address": poi.get("address", "") or "",
                            "district": f"{poi.get('pname', '')}{poi.get('cityname', '')}{poi.get('adname', '')}"
                        })
                result = {
                    "status": "1",
                    "tips": tips
                }
                # 写入缓存
                self._cache.set_inputtips(keywords, result)
                return result
            return {"status": "0", "info": data.get("info", "查询失败")}

        except Exception as e:
            logger.error(f"输入提示失败: {e}")
            return {"status": "0", "info": str(e)}

    def plan_segment(self, from_loc: Dict, to_loc: Dict, strategy: str, strategy_param: str = None) -> Dict:
        """规划单段路径（单次 API 调用）

        Args:
            from_loc: {"name": str, "lng": float, "lat": float}
            to_loc: {"name": str, "lng": float, "lat": float}
            strategy: driving|walking|riding|transit
            strategy_param: 高德 API 的 strategy 参数值，如 "0", "32", "33" 等

        Returns:
            {"status": "success", "distance": int, "duration": int, "path": [[lng, lat], ...], "steps": [...]}
            {"status": "error", "error": str}
        """
        # 先查缓存
        cached = self._cache.get_route(
            from_loc['lng'], from_loc['lat'],
            to_loc['lng'], to_loc['lat'],
            strategy, strategy_param
        )
        if cached:
            logger.info(f"plan_segment 缓存命中: {from_loc['name']} -> {to_loc['name']}")
            return cached

        origin = f"{from_loc['lng']},{from_loc['lat']}"
        destination = f"{to_loc['lng']},{to_loc['lat']}"

        params = {
            "key": self.amap_key,
            "origin": origin,
            "destination": destination
        }

        # 公交需要 city 参数
        if strategy == "transit":
            params["city"] = "全国"
            url = f"{AMAP_DIRECTION_URL}/transit/integrated"
        else:
            url = f"{AMAP_DIRECTION_URL}/{strategy}"
            # 驾车/骑行可指定 strategy 参数
            if strategy in ("driving", "riding") and strategy_param:
                params["strategy"] = strategy_param

        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if data.get("status") != "1":
                return {"status": "error", "error": data.get("info", "API 调用失败")}

            result = self._parse_single_response(strategy, data, from_loc, to_loc, strategy_param)

            # 写入缓存
            if result.get("status") == "success":
                self._cache.set_route(
                    from_loc['lng'], from_loc['lat'],
                    to_loc['lng'], to_loc['lat'],
                    strategy, result, strategy_param
                )

            return result

        except Exception as e:
            logger.error(f"路径规划 API 调用失败: {e}")
            return {"status": "error", "error": str(e)}

    def plan_segment_with_strategies(self, from_loc: Dict, to_loc: Dict, strategy: str, strategy_plan: str) -> Dict:
        """规划单段路径（多次 API 调用获取多方案）

        Args:
            from_loc: {"name": str, "lng": float, "lat": float}
            to_loc: {"name": str, "lng": float, "lat": float}
            strategy: driving|walking|riding|transit
            strategy_plan: 策略方案，如 "recommended", "shortest", "avoid_toll"

        Returns:
            {"status": "success", "distance": int, "duration": int, "path": [[lng, lat], ...],
             "steps": [...], "options": [...], "strategy_plan": str}
            {"status": "error", "error": str}
        """
        # 非驾车只调用一次
        if strategy != "driving":
            result = self.plan_segment(from_loc, to_loc, strategy)
            if result.get("status") != "success":
                return result
            return {
                "status": "success",
                "distance": result["distance"],
                "duration": result["duration"],
                "path": result.get("path", []),
                "steps": result.get("steps", []),
                "options": [result],
                "strategy_plan": None
            }

        # 驾车：调用多次获取多方案
        plan_config = DRIVING_STRATEGY_PLANS.get(strategy_plan, DRIVING_STRATEGY_PLANS["recommended"])
        strategy_params = plan_config["strategies"]

        options = []
        first_success = None

        for param in strategy_params:
            result = self.plan_segment(from_loc, to_loc, strategy, param)
            if result.get("status") == "success":
                result["strategy_param"] = param
                result["strategy_label"] = AMAP_DRIVING_STRATEGY_PARAMS.get(param, param)
                options.append(result)
                if first_success is None:
                    first_success = result

        if not options:
            return {"status": "error", "error": "所有策略方案均失败"}

        # 去重处理
        options = self._deduplicate_options(options)

        # 使用第一个成功的结果作为默认显示
        return {
            "status": "success",
            "distance": first_success["distance"],
            "duration": first_success["duration"],
            "path": first_success.get("path", []),
            "steps": first_success.get("steps", []),
            "options": options,
            "strategy_plan": strategy_plan
        }

    def _deduplicate_options(self, options: List[Dict]) -> List[Dict]:
        """去重：距离差<5% 且 时间差<10% 的方案只保留一个

        Args:
            options: 原始方案列表

        Returns:
            去重后的方案列表
        """
        if not options:
            return []
        if len(options) == 1:
            return options

        result = [options[0]]  # 保留第一个

        for opt in options[1:]:
            is_duplicate = False
            for kept in result:
                # 计算距离和时间差异百分比
                dist_diff = abs(opt['distance'] - kept['distance']) / max(kept['distance'], 1)
                time_diff = abs(opt['duration'] - kept['duration']) / max(kept['duration'], 1)

                # 如果距离和时间都差不多，认为是重复
                if dist_diff < ROUTE_DEDUP_DISTANCE_THRESHOLD and time_diff < ROUTE_DEDUP_TIME_THRESHOLD:
                    is_duplicate = True
                    break

            if not is_duplicate:
                result.append(opt)

        return result

    def plan_route(self, segments: List[Dict]) -> Dict:
        """规划多段路径

        Args:
            segments: [
                {"from": {"name": str, "lng": float, "lat": float},
                 "to": {"name": str, "lng": float, "lat": float},
                 "strategy": "driving|walking|riding|transit",
                 "strategy_plan": "recommended"|"shortest"|"avoid_toll"},  # 驾车策略方案
                ...
            ]

        Returns:
            {"status": "success", "total_distance": int, "total_duration": int, "segments": [...]}
            {"status": "error", "error": str}
        """
        if not segments:
            return {"status": "error", "error": "缺少路段信息"}

        results = []
        total_distance = 0
        total_duration = 0

        for i, segment in enumerate(segments):
            from_loc = segment.get("from")
            to_loc = segment.get("to")
            strategy = segment.get("strategy", "driving")
            strategy_plan = segment.get("strategy_plan", "recommended") if strategy == "driving" else None

            if not from_loc or not to_loc:
                return {"status": "error", "error": f"第 {i+1} 段缺少起终点信息"}

            # 验证坐标
            if not all(k in from_loc for k in ("lng", "lat")):
                return {"status": "error", "error": f"第 {i+1} 段起点坐标无效"}
            if not all(k in to_loc for k in ("lng", "lat")):
                return {"status": "error", "error": f"第 {i+1} 段终点坐标无效"}

            # 使用多策略方案（驾车时）
            if strategy == "driving" and strategy_plan:
                result = self.plan_segment_with_strategies(from_loc, to_loc, strategy, strategy_plan)
            else:
                result = self.plan_segment(from_loc, to_loc, strategy)

            if result.get("status") != "success":
                return result

            segment_result = {
                "from": from_loc,
                "to": to_loc,
                "strategy": strategy,
                "distance": result["distance"],
                "duration": result["duration"],
                "path": result.get("path", []),
                "steps": result.get("steps", [])
            }

            # 如果有多方案，添加到结果中
            if result.get("options"):
                segment_result["options"] = result["options"]
                segment_result["strategy_plan"] = result.get("strategy_plan")

            results.append(segment_result)

            total_distance += result["distance"]
            total_duration += result["duration"]

        return {
            "status": "success",
            "total_distance": total_distance,
            "total_duration": total_duration,
            "segments": results
        }

    def _parse_single_response(self, strategy: str, data: Dict, from_loc: Dict, to_loc: Dict, strategy_param: str = None) -> Dict:
        """解析单次 API 响应"""
        if strategy == "transit":
            return self._parse_transit_response(data, from_loc, to_loc)
        else:
            return self._parse_directional_single_response(strategy, data, from_loc, to_loc, strategy_param)

    def _parse_directional_single_response(self, strategy: str, data: Dict, from_loc: Dict, to_loc: Dict, strategy_param: str = None) -> Dict:
        """解析驾车/步行/骑行单次响应"""
        route = data.get("route", {})
        paths = route.get("paths", [])

        if not paths:
            return {"status": "error", "error": "未找到可行路线"}

        # 取第一条（推荐方案）
        first = paths[0]
        distance = int(first.get("distance", 0))
        duration = int(first.get("duration", 0))
        polyline = self._extract_path_from_steps(first)
        steps = self._extract_steps(first)

        return {
            "status": "success",
            "distance": distance,
            "duration": duration,
            "path": polyline,
            "steps": steps
        }

    def _extract_path_from_steps(self, path: Dict) -> List[List[float]]:
        """从 steps 中提取完整路线坐标"""
        result = []
        for step in path.get("steps", []):
            polyline = step.get("polyline", "")
            if polyline:
                # polyline 是用分号分隔的 "lng,lat" 字符串
                for coord in polyline.split(";"):
                    if "," in coord:
                        parts = coord.split(",")
                        if len(parts) == 2:
                            try:
                                lng = float(parts[0])
                                lat = float(parts[1])
                                result.append([lng, lat])
                            except ValueError:
                                continue
        return result

    def _parse_transit_response(self, data: Dict, from_loc: Dict, to_loc: Dict) -> Dict:
        """解析公交响应"""
        route = data.get("route", {})
        transits = route.get("transits", [])

        if not transits:
            return {"status": "error", "error": "未找到可行公交路线"}

        # 取第一条方案
        first = transits[0]
        distance = int(first.get("distance", 0))
        duration = int(first.get("duration", 0))

        return {
            "status": "success",
            "distance": distance,
            "duration": duration,
            "path": [],
            "steps": self._extract_transit_steps(first)
        }

    def _extract_steps(self, path: Dict) -> List[Dict]:
        """提取分段信息"""
        steps = []
        for step in path.get("steps", []):
            steps.append({
                "instruction": step.get("instruction", ""),
                "road": step.get("road", ""),
                "distance": int(step.get("distance", 0)),
                "duration": int(step.get("duration", 0))
            })
        return steps

    def _extract_transit_steps(self, transit: Dict) -> List[Dict]:
        """提取公交分段信息"""
        segments = transit.get("segments", [])
        steps = []

        for seg in segments:
            # 步行段
            if seg.get("walking"):
                walk = seg["walking"]
                steps.append({
                    "instruction": f"步行 {walk.get('distance', 0)} 米",
                    "road": "",
                    "distance": int(walk.get("distance", 0)),
                    "duration": int(walk.get("duration", 0))
                })

            # 公交段
            if seg.get("bus"):
                bus = seg["bus"]
                buslines = bus.get("buslines", [])
                if buslines:
                    line = buslines[0]
                    steps.append({
                        "instruction": f"乘坐 {line.get('name', '')}",
                        "road": "",
                        "distance": int(seg.get("distance", 0)),
                        "duration": int(seg.get("duration", 0))
                    })

        return steps
