"""路书 RoadBook - CLI 入口"""
import os
import sys
import json
import logging

# 打包后运行：sys._MEIPASS 是 PyInstaller 解压临时资源的目录
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # 确保 src 目录在 path 中
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
    APP_DIR = BASE_DIR

# 添加父目录到 path（用于导入 src 包）
parent_dir = os.path.dirname(BASE_DIR)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 动态导入 config（解决 PyInstaller 打包问题）
import importlib.util
if getattr(sys, 'frozen', False):
    # frozen 模式：datas 中的 'src/config.py' 被提取到 BASE_DIR（不是 BASE_DIR/src/）
    config_path = os.path.join(BASE_DIR, 'config.py')
else:
    # 开发模式：config.py 在 src/ 目录下（photo_track.py 本身就在 src/ 下）
    config_path = os.path.join(BASE_DIR, 'config.py')
config_spec = importlib.util.spec_from_file_location("config", config_path)
config = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(config)

from track_generator import (
    filter_nearby_points, segment_points_by_day, collect_photo_points,
    resolve_place_names, render_html_template, render_html_template_single,
    generate_original_json, generate_converted_json, render_timeline_template
)
from geo_coder import get_geocode_cache

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(APP_DIR, 'travellingMap.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def main(photo_dir_name: str = None, skip_parse: bool = False,
         distance_threshold: int = None, time_threshold: int = None):
    """主入口

    Args:
        photo_dir_name: 照片目录名（相对于 photo 文件夹）
        skip_parse: 是否跳过图片解析，仅生成 HTML
        distance_threshold: 距离阈值（米），覆盖 config.py 中的配置
        time_threshold: 时间阈值（秒），覆盖 config.py 中的配置
    """
    DISTANCE_THRESHOLD = config.DISTANCE_THRESHOLD
    TIME_THRESHOLD = config.TIME_THRESHOLD
    SUPPORTED_FORMATS = config.SUPPORTED_FORMATS
    SINGLE_HTML_OUTPUT = config.SINGLE_HTML_OUTPUT
    AMAP_SERVER_AK = config.AMAP_SERVER_AK
    get_photo_base_dir = config.get_photo_base_dir
    get_output_base_dir = config.get_output_base_dir

    # 如果没有指定目录名，从命令行参数获取
    if photo_dir_name is None:
        import argparse
        parser = argparse.ArgumentParser(
            description='路书 - 照片 GPS 轨迹生成器',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog='''
示例:
  python photo_track.py test_photos
  python photo_track.py test_photos -d 500 -t 1800
  python photo_track.py test_photos -H
            '''
        )
        parser.add_argument('photo_dir', help='照片目录名（相对于 photo/ 文件夹）',
                            nargs='?', default=None)
        parser.add_argument('--html-only', '-H', action='store_true',
                            help='跳过图片解析，仅生成 HTML')
        parser.add_argument('--distance-threshold', '-d', type=int, default=None,
                            help='距离阈值（米），覆盖 config.py 中的配置')
        parser.add_argument('--time-threshold', '-t', type=int, default=None,
                            help='时间阈值（秒），覆盖 config.py 中的配置')
        parser.add_argument('--verbose', '-v', action='store_true',
                            help='显示详细日志')

        args = parser.parse_args()

        if args.photo_dir is None:
            logger.info("\n用法: python photo_track.py <照片目录名> [选项]")
            logger.info("示例: python photo_track.py test1")
            logger.info("\n照片目录应放在: travellingMap/photo/<目录名>/")
            logger.info("\n使用 --help 查看所有选项")
            return

        photo_dir_name = args.photo_dir
        skip_parse = args.html_only
        distance_threshold = args.distance_threshold
        time_threshold = args.time_threshold
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

    # 使用 CLI 参数覆盖默认值
    if distance_threshold is None:
        distance_threshold = DISTANCE_THRESHOLD
    if time_threshold is None:
        time_threshold = TIME_THRESHOLD

    logger.info("=" * 50)
    logger.info("路书 - 照片 GPS 轨迹生成器")
    logger.info("=" * 50)
    logger.info(f"距离阈值: {distance_threshold} 米")
    logger.info(f"时间阈值: {time_threshold} 秒")

    # 构建路径
    photo_folder = os.path.join(get_photo_base_dir(), photo_dir_name)
    output_folder = os.path.join(get_output_base_dir(), photo_dir_name)

    # 确保输出目录存在
    os.makedirs(output_folder, exist_ok=True)

    logger.info(f"照片文件夹: {photo_folder}")
    logger.info(f"输出文件夹: {output_folder}")

    # 非 HTML-only 模式：删除 output 文件夹内容，准备重新处理
    if not skip_parse:
        logger.info("删除 output 文件夹内容，准备重新处理...")
        for item in os.listdir(output_folder):
            item_path = os.path.join(output_folder, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                import shutil
                shutil.rmtree(item_path)

    # 获取缓存
    cache = get_geocode_cache(os.path.join(config.APP_DIR, 'cache'), config.CACHE_TYPE)

    # --html-only 模式：跳过图片解析，直接加载已有 JSON
    if skip_parse:
        logger.info("HTML-only 模式：跳过图片解析")
        json_path = os.path.join(output_folder, 'data_converted.json')
        if not os.path.exists(json_path):
            logger.error("data_converted.json 不存在，请先完整运行一次")
            return
        with open(json_path, 'r', encoding='utf-8') as f:
            filtered_points = json.load(f)
        logger.info(f"已加载治理数据: {json_path} ({len(filtered_points)} 条)")
    else:
        # 收集轨迹点
        logger.info("正在扫描照片...")
        points, unknown_points = collect_photo_points(photo_folder, output_folder, SUPPORTED_FORMATS)

        if not points:
            logger.error("未找到有效轨迹点！")
            logger.error("请确认照片文件夹中有带 GPS 信息的照片。")
            # 仍然生成 unknown JSON 以记录所有照片
            generate_original_json([], output_folder, unknown_points)
            return

        logger.info(f"找到 {len(points)} 个有效轨迹点, {len(unknown_points)} 个无 GPS 照片")

        # 批量解析地点名称（在生成原始数据之前）
        if AMAP_SERVER_AK:
            points = resolve_place_names(points, AMAP_SERVER_AK, cache)
        else:
            logger.warning("未配置高德 Web 服务 API Key，无法解析地点信息")
            for point in points:
                point['place_name'] = '未知地点'
                point['address'] = ''
                point['administrative'] = {'province': '', 'city': '', 'district': ''}

        # 生成原始数据 JSON（此时已包含地点信息）
        logger.info("正在生成原始数据 JSON...")
        generate_original_json(points, output_folder, unknown_points)

        # 过滤相近坐标（使用配置的阈值）
        logger.info(f"正在合并相近坐标（{distance_threshold}米/{time_threshold}秒内）...")
        filtered_points = filter_nearby_points(points, distance_threshold, time_threshold)
        logger.info(f"合并后剩余 {len(filtered_points)} 个有效点")

        # 轨迹分段（识别第1天/第2天/...）
        logger.info("正在进行轨迹分段...")
        filtered_points = segment_points_by_day(filtered_points)

        # 生成治理后数据 JSON
        logger.info("正在生成治理数据 JSON...")
        generate_converted_json(filtered_points, output_folder)

    # 获取模板和静态文件目录
    # frozen 模式下在 BASE_DIR，开发模式下在 APP_DIR
    if getattr(sys, 'frozen', False):
        templates_dir = os.path.join(config.BASE_DIR, 'templates')
        static_dir = os.path.join(config.BASE_DIR, 'static')
    else:
        templates_dir = os.path.join(config.APP_DIR, 'templates')
        static_dir = os.path.join(config.APP_DIR, 'static')

    # 生成 HTML
    logger.info("正在生成 HTML 文件...")
    output_html = os.path.join(output_folder, 'track_output.html')

    if SINGLE_HTML_OUTPUT:
        render_html_template_single(filtered_points, unknown_points, output_folder, output_html, templates_dir, static_dir, config.AMAP_WEB_AK)
    else:
        render_html_template(filtered_points, output_html, templates_dir, static_dir, config.AMAP_WEB_AK)

    # 生成时间轴页面
    logger.info("正在生成时间轴页面...")
    timeline_output = os.path.join(output_folder, 'timeline.html')
    render_timeline_template(filtered_points, output_folder, timeline_output, templates_dir, static_dir)

    logger.info("文件列表:")
    logger.info("  - data_original.json (原始数据)")
    logger.info("  - data_converted.json (治理数据)")
    logger.info("  - track_output.html (轨迹地图)")
    logger.info("  - timeline.html (时间轴页面)")


if __name__ == '__main__':
    main()
