# 配置文件
import os
import sys
from dotenv import load_dotenv

# 打包后运行：sys._MEIPASS 是 PyInstaller 解压临时资源的目录
_is_frozen = getattr(sys, 'frozen', False)
if _is_frozen:
    # 打包后运行，资源在临时目录
    BASE_DIR = sys._MEIPASS
    # exe 所在目录作为数据目录（存放 photo、output、cache）
    APP_DIR = os.path.dirname(sys.executable)
else:
    # 开发环境
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # config.py 在 src/ 目录下时，APP_DIR 应该是项目根目录
    if os.path.basename(BASE_DIR) == 'src':
        APP_DIR = os.path.dirname(BASE_DIR)
    else:
        APP_DIR = BASE_DIR

# 加载 .env 文件
env_path = os.path.join(APP_DIR, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
elif os.path.exists('.env'):
    load_dotenv('.env')

# 高德地图 Web 端 Key（用于地图展示 AMap.Map）
AMAP_WEB_AK = os.getenv('AMAP_WEB_AK', '')

# 高德地图 Web 服务 Key（用于逆地理编码 API）
AMAP_SERVER_AK = os.getenv('AMAP_SERVER_AK', '')

# 缩略图大小
THUMBNAIL_SIZE = (400, 400)

# 原图压缩质量 (1-100)，数值越小文件越小但质量越低
ORIGINAL_IMAGE_QUALITY = 50

# 坐标合并阈值 - 距离阈值（米），默认1000米（1公里）
DISTANCE_THRESHOLD = 1000

# 坐标合并阈值 - 时间阈值（秒），默认7200秒（2小时）
TIME_THRESHOLD = 7200

# 支持的图片格式
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.heic'}

# 单一 HTML 文件输出（将所有资源内联到 HTML 中，方便离线分享）
SINGLE_HTML_OUTPUT = False

# 缓存类型: 'sqlite' 或 'json'
CACHE_TYPE = os.getenv('CACHE_TYPE', 'sqlite')

# 照片根目录（可配置为绝对路径，如 D:\photos\）
# 支持相对路径（相对于 APP_DIR）和绝对路径
# 默认为 "photo" 子目录（相对于 exe 所在目录）
# 相对路径格式：以 \ 开头表示相对于 APP_DIR，如 \photo
PHOTO_BASE_DIR = os.getenv('PHOTO_BASE_DIR', 'photo')

def get_photo_base_dir():
    """获取照片根目录的绝对路径"""
    # 优先检查相对路径格式（以 \ 开头表示相对于 APP_DIR）
    if PHOTO_BASE_DIR.startswith('\\'):
        # \photo 表示相对于 APP_DIR
        return os.path.join(APP_DIR, PHOTO_BASE_DIR[1:])
    if os.path.isabs(PHOTO_BASE_DIR):
        return PHOTO_BASE_DIR
    return os.path.join(APP_DIR, PHOTO_BASE_DIR)

# 输出根目录（可配置）
OUTPUT_BASE_DIR = os.getenv('OUTPUT_BASE_DIR', 'output')

def get_output_base_dir():
    """获取输出根目录的绝对路径"""
    # 优先检查相对路径格式（以 \ 开头表示相对于 APP_DIR）
    if OUTPUT_BASE_DIR.startswith('\\'):
        # \output 表示相对于 APP_DIR
        return os.path.join(APP_DIR, OUTPUT_BASE_DIR[1:])
    if os.path.isabs(OUTPUT_BASE_DIR):
        return OUTPUT_BASE_DIR
    return os.path.join(APP_DIR, OUTPUT_BASE_DIR)

# 端口配置
WEB_PORT = int(os.getenv('WEB_PORT', 18443))      # 网页端默认端口
DESKTOP_PORT = int(os.getenv('DESKTOP_PORT', 12255))  # 桌面端默认端口

# 驾车策略配置（高德API）
# - 推荐方案: 32 + 0 + 1 + 2 + 33 = 5策略 → 去重显示
# - 最短路线: 37 + 34 + 35 + 38 + 33 = 5策略 → 去重显示
# - 避免收费: 1 + 36 + 42 + 43 + 40 = 5策略 → 去重显示

DRIVING_STRATEGY_PLANS = {
    "recommended": {
        "label": "推荐方案",
        "strategies": ["32", "0", "1", "2", "33"]
    },
    "shortest": {
        "label": "最短路线",
        "strategies": ["33", "39", "40", "41", "43"]
    },
    "avoid_toll": {
        "label": "避免收费",
        "strategies": ["1", "36", "42", "43", "40"]
    }
}

# 高德 API 驾车算路策略参数说明
AMAP_DRIVING_STRATEGY_PARAMS = {
    "0": "速度优先（不一定距离最短）",
    "1": "费用优先（不走收费路段）",
    "2": "常规最快（综合距离/耗时）",
    "32": "高德推荐（APP默认）",
    "33": "躲避拥堵",
    "34": "高速优先",
    "35": "不走高速",
    "36": "少收费",
    "37": "大路优先",
    "38": "速度最快",
    "39": "躲避拥堵+高速优先",
    "40": "躲避拥堵+不走高速",
    "41": "躲避拥堵+少收费",
    "42": "少收费+不走高速",
    "43": "躲避拥堵+少收费+不走高速",
    "44": "躲避拥堵+大路优先",
    "45": "躲避拥堵+速度最快"
}

# 路线去重阈值
ROUTE_DEDUP_DISTANCE_THRESHOLD = 0.05  # 距离差异<5%认为重复
ROUTE_DEDUP_TIME_THRESHOLD = 0.10      # 时间差异<10%认为重复

# DeepSeek AI API 配置 https://api.deepseek.com/v1
# DEEPSEEK_MODEL: deepseek-chat、deepseek-reasoner
# DEEPSEEK_API_URL: https://api.deepseek.com、https://api.deepseek.com/v1
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = os.getenv('DEEPSEEK_API_URL', 'https://api.deepseek.com')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-reasoner')

# 天气信息配置（默认显示天气）
SHOW_WEATHER_INFO = os.getenv('SHOW_WEATHER_INFO', 'true').lower() == 'true'

# 详情路径规划包含的 route_stops 类型
# 可选类型: start, gas, transit, scenic, food, accommodation, end
# 默认包含 start, end, scenic, accommodation（排除 gas/transit/food 减少节点数）
ROUTE_DETAIL_STOP_TYPES = os.getenv('ROUTE_DETAIL_STOP_TYPES', 'start,end,scenic,accommodation').split(',')

# AI 路书输出模块配置
# 可选模块: basic_info, scenic_guides, daily_itinerary, budget, checklist
# 默认全部启用，逗号分隔
# AI_ROUTE_OUTPUT_MODULES = os.getenv('AI_ROUTE_OUTPUT_MODULES', 'basic_info,scenic_guides,daily_itinerary,budget,checklist').split(',')
AI_ROUTE_OUTPUT_MODULES = os.getenv('AI_ROUTE_OUTPUT_MODULES', 'basic_info,daily_itinerary').split(',')
