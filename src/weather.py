"""天气查询模块 - 高德天气 API"""
import requests
import logging

logger = logging.getLogger(__name__)

# 高德天气 API
AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"

# 天气图标映射
WEATHER_ICONS = {
    "晴": "☀️",
    "多云": "⛅",
    "阴": "☁️",
    "沙尘": "🌫️",
    "雪": "❄️",
    "雨夹雪": "🌨️",
    "小雨": "🌦️",
    "中雨": "🌧️",
    "大雨": "🌧️",
    "暴雨": "⛈️",
    "大暴雨": "⛈️",
    "特大暴雨": "⛈️",
    "雷阵雨": "⛈️",
    "阵雨": "🌦️",
    "雾": "🌫️",
    "霾": "🌫️",
    "扬沙": "🌫️",
    "浮尘": "🌫️",
    "雾霾": "🌫️",
}


def get_weather_icon(weather: str) -> str:
    """获取天气图标"""
    if not weather:
        return "🌤️"
    # 精确匹配
    if weather in WEATHER_ICONS:
        return WEATHER_ICONS[weather]
    # 模糊匹配
    for key, icon in WEATHER_ICONS.items():
        if key in weather:
            return icon
    return "🌤️"


def get_weather(city: str, api_key: str) -> dict:
    """获取天气（高德天气 API）

    Args:
        city: 城市名称（如"北京"、"大理"）
        api_key: 高德地图 API Key（使用 AMAP_SERVER_AK）

    Returns:
        {"status": "success", "weather": {...}, "location_name": "城市名"}
        {"status": "error", "error": str}
    """
    if not api_key:
        return {"status": "error", "error": "API Key 未配置"}

    try:
        # 先通过高德地理编码获取城市编码
        geo_url = "https://restapi.amap.com/v3/geocode/geo"
        geo_params = {
            "key": api_key,
            "address": city,
            "output": "json"
        }

        geo_resp = requests.get(geo_url, params=geo_params, timeout=5)
        geo_data = geo_resp.json()

        city_code = None
        city_name = city

        # 检查地理编码结果
        city_code = None
        city_name = city
        if geo_data.get("status") == "1":
            geocodes = geo_data.get("geocodes")
            if geocodes and isinstance(geocodes, list) and len(geocodes) > 0:
                geo = geocodes[0]
                # 确保 geo 是字典类型
                if isinstance(geo, dict):
                    # 优先使用 adcode（行政区编码），天气API主要依赖adcode
                    city_code = geo.get("adcode")
                    # citycode 可能是空的，但 adcode 通常都有值
                    city_name = geo.get("city") or geo.get("province") or city
                    logger.info(f"地理编码成功: {city} -> adcode={city_code}, geo={geo}")

        if not city_code:
            # 尝试直接使用城市名作为编码
            city_code = city
            logger.warning(f"无法获取城市编码，使用原始城市名: {city}")

        # 查询天气
        weather_params = {
            "key": api_key,
            "city": city_code,
            "extensions": "base",  # base=实时天气，all=预报天气
            "output": "json"
        }

        weather_resp = requests.get(AMAP_WEATHER_URL, params=weather_params, timeout=5)
        weather_data = weather_resp.json()
        logger.info(f"天气API响应: {weather_data}, city_code={city_code}")

        if weather_data.get("status") == "1":
            lives = weather_data.get("lives")
            logger.info(f"lives 类型: {type(lives)}, 值: {lives}")
            lives = weather_data.get("lives")
            if lives and isinstance(lives, list) and len(lives) > 0:
                live = lives[0]
                # 确保 live 是字典类型
                if isinstance(live, dict):
                    weather_str = live.get("weather", "")

                    return {
                        "status": "success",
                        "location_name": live.get("city", city_name),
                        "weather": {
                            "temp": live.get("temperature"),          # 温度
                            "feelsLike": live.get("temperature_float"),  # 体感温度
                            "text": weather_str,                      # 天气文字
                            "icon": get_weather_icon(weather_str),
                            "windDir": live.get("winddirection"),     # 风向
                            "windScale": live.get("windpower"),      # 风力等级
                            "humidity": live.get("humidity"),        # 湿度
                        }
                    }
                else:
                    return {"status": "error", "error": "天气数据格式错误"}
            return {"status": "error", "error": "未找到天气数据"}

        return {"status": "error", "error": weather_data.get("info", "获取失败")}

    except Exception as e:
        logger.error(f"天气查询失败: {e}")
        return {"status": "error", "error": str(e)}
