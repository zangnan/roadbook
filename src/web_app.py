"""路书 RoadBook - Web 界面"""
import os
import sys
import json
import uuid
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file, abort, Response

# 打包后运行：sys._MEIPASS 是 PyInstaller 解压临时资源的目录
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # 确保 src 目录在 path 中
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
    # web_app.py 在 src/ 目录下时，APP_DIR 应该是项目根目录
    if os.path.basename(BASE_DIR) == 'src':
        APP_DIR = os.path.dirname(BASE_DIR)
    else:
        APP_DIR = BASE_DIR

# 动态导入 config（解决 PyInstaller 打包问题）
import importlib.util
if getattr(sys, 'frozen', False):
    # frozen 模式：datas 中的 'src/config.py' 被提取到 BASE_DIR（不是 BASE_DIR/src/）
    config_path = os.path.join(BASE_DIR, 'config.py')
else:
    # 开发模式：config.py 在 src/ 目录下（web_app.py 本身就在 src/ 下）
    config_path = os.path.join(BASE_DIR, 'config.py')
config_spec = importlib.util.spec_from_file_location("config", config_path)
config = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(config)

CONFIG_BASE_DIR = config.BASE_DIR
AMAP_WEB_AK = config.AMAP_WEB_AK
AMAP_SERVER_AK = config.AMAP_SERVER_AK
THUMBNAIL_SIZE = config.THUMBNAIL_SIZE
ORIGINAL_IMAGE_QUALITY = config.ORIGINAL_IMAGE_QUALITY
DISTANCE_THRESHOLD = config.DISTANCE_THRESHOLD
TIME_THRESHOLD = config.TIME_THRESHOLD
SUPPORTED_FORMATS = config.SUPPORTED_FORMATS
SINGLE_HTML_OUTPUT = config.SINGLE_HTML_OUTPUT
CACHE_TYPE = config.CACHE_TYPE
PHOTO_BASE_DIR = config.PHOTO_BASE_DIR
OUTPUT_BASE_DIR = config.OUTPUT_BASE_DIR
get_photo_base_dir = config.get_photo_base_dir
get_output_base_dir = config.get_output_base_dir
CONFIG_APP_DIR = config.APP_DIR
WEB_PORT = config.WEB_PORT
DESKTOP_PORT = config.DESKTOP_PORT
DEEPSEEK_API_KEY = config.DEEPSEEK_API_KEY
DEEPSEEK_API_URL = config.DEEPSEEK_API_URL
DEEPSEEK_MODEL = config.DEEPSEEK_MODEL
SHOW_WEATHER_INFO = config.SHOW_WEATHER_INFO

# 确保运行时目录存在（photo、output、cache）
for dir_name in ['photo', 'output', 'cache']:
    dir_path = os.path.join(CONFIG_APP_DIR, dir_name)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# Flask 配置
# frozen 模式下，templates 和 static 在 BASE_DIR；开发模式下在 APP_DIR
if getattr(sys, 'frozen', False):
    flask_template_folder = os.path.join(BASE_DIR, 'templates')
    flask_static_folder = os.path.join(BASE_DIR, 'static')
else:
    flask_template_folder = os.path.join(CONFIG_APP_DIR, 'templates')
    flask_static_folder = os.path.join(CONFIG_APP_DIR, 'static')

app = Flask(__name__,
            template_folder=flask_template_folder,
            static_folder=flask_static_folder)
app.config['BASE_DIR'] = BASE_DIR
app.config['APP_DIR'] = CONFIG_APP_DIR

# 任务存储 (生产环境应使用 Redis)
tasks = {}


def get_photo_dirs():
    """获取可用的照片目录列表"""
    photo_base = get_photo_base_dir()
    if not os.path.exists(photo_base):
        return []
    return sorted([d for d in os.listdir(photo_base)
                   if os.path.isdir(os.path.join(photo_base, d))])


def get_output_dirs():
    """获取已生成的输出目录列表"""
    output_base = get_output_base_dir()
    if not os.path.exists(output_base):
        return []
    dirs = []
    for d in os.listdir(output_base):
        full_path = os.path.join(output_base, d)
        if os.path.isdir(full_path):
            # 检查是否有 track_output.html
            has_output = os.path.exists(os.path.join(full_path, 'track_output.html'))
            has_timeline = os.path.exists(os.path.join(full_path, 'timeline.html'))
            mtime = os.path.getmtime(full_path)
            dirs.append({
                'name': d,
                'has_output': has_output,
                'has_timeline': has_timeline,
                'mtime': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            })
    return sorted(dirs, key=lambda x: x['mtime'], reverse=True)


def run_photo_track(task_id, photo_dir, distance_threshold, time_threshold, html_only):
    """后台执行 photo_track.py（直接调用函数，避免 subprocess 问题）"""
    import logging
    from io import StringIO

    tasks[task_id]['status'] = 'running'

    # 创建日志处理器，实时捕获日志输出
    class LogCapture(logging.Handler):
        def __init__(self, task_id, tasks):
            super().__init__()
            self.task_id = task_id
            self.tasks = tasks

        def emit(self, record):
            try:
                msg = self.format(record)
                self.tasks[self.task_id]['output'].append({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'text': msg
                })
                # 保持最多 500 行
                if len(self.tasks[self.task_id]['output']) > 500:
                    self.tasks[self.task_id]['output'] = self.tasks[self.task_id]['output'][-500:]
            except Exception:
                pass

    # 要捕获的日志器列表
    loggers_to_capture = ['photo_track', 'geo_coder', 'track_generator']

    try:
        # 添加日志处理器
        log_capture = LogCapture(task_id, tasks)
        log_capture.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        # 添加到多个相关日志器（photo_track 及其子模块）
        # photo_track.py 中的 logger = logging.getLogger(__name__) -> 'photo_track'
        # geo_coder.py 中的 logger = logging.getLogger(__name__) -> 'geo_coder'
        # track_generator.py 中的 logger = logging.getLogger(__name__) -> 'track_generator'
        for logger_name in loggers_to_capture:
            logger = logging.getLogger(logger_name)
            logger.addHandler(log_capture)

        # 动态导入 photo_track 模块
        from photo_track import main as photo_track_main

        # 直接调用 main 函数
        skip_parse = html_only
        photo_track_main(
            photo_dir_name=photo_dir,
            skip_parse=skip_parse,
            distance_threshold=distance_threshold,
            time_threshold=time_threshold
        )

        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['output_dir'] = photo_dir

    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['output'].append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'text': f'执行错误: {str(e)}'
        })
        import traceback
        tasks[task_id]['output'].append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'text': traceback.format_exc()
        })
    finally:
        # 移除日志处理器
        for logger_name in loggers_to_capture:
            logger = logging.getLogger(logger_name)
            if log_capture in logger.handlers:
                logger.removeHandler(log_capture)


@app.route('/route')
def route_page():
    """路径规划页面"""
    return render_template('route_template.html',
                           amap_ak=AMAP_WEB_AK)


@app.route('/roadbook')
def roadbook_page():
    """路书模板页面"""
    return render_template('roadbook_template.html',
                           static_base='',
                           show_weather=SHOW_WEATHER_INFO,
                           route_detail_stop_types=config.ROUTE_DETAIL_STOP_TYPES)


@app.route('/')
def home_page():
    """首页 - 功能门户"""
    output_dirs = get_output_dirs()
    return render_template('home_template.html',
                           static_base='',
                           outputs=output_dirs)


@app.route('/photo-track')
def photo_track_page():
    """照片轨迹页面"""
    photo_dirs = get_photo_dirs()
    output_dirs = get_output_dirs()
    return render_template('config_template.html',
                           static_base='',
                           photo_dirs=photo_dirs,
                           output_dirs=output_dirs,
                           config_base=CONFIG_APP_DIR,
                           photo_base=get_photo_base_dir(),
                           output_base=get_output_base_dir(),
                           config={
                               'distance_threshold': DISTANCE_THRESHOLD,
                               'time_threshold': TIME_THRESHOLD,
                               'thumbnail_width': THUMBNAIL_SIZE[0],
                               'thumbnail_height': THUMBNAIL_SIZE[1],
                               'image_quality': ORIGINAL_IMAGE_QUALITY,
                               'single_html': SINGLE_HTML_OUTPUT,
                               'cache_type': CACHE_TYPE,
                               'amap_web_ak': AMAP_WEB_AK[:10] + '...' if AMAP_WEB_AK else '',
                               'amap_server_ak': AMAP_SERVER_AK[:10] + '...' if AMAP_SERVER_AK else '',
                           })


@app.route('/api/route/geocode', methods=['POST'])
def api_route_geocode():
    """地理编码：地址转坐标"""
    data = request.json
    address = data.get('address', '').strip()

    if not address:
        return jsonify({'status': 'error', 'error': '地址不能为空'}), 400

    from route_planner import RoutePlanner
    planner = RoutePlanner(AMAP_SERVER_AK)
    result = planner.geocode(address)

    return jsonify(result)


@app.route('/api/route/inputtips', methods=['POST'])
def api_route_inputtips():
    """输入提示：高德 v3/place/text"""
    data = request.json
    keywords = data.get('keywords', '').strip()

    if not keywords or len(keywords) < 2:
        return jsonify({'status': '0', 'info': '关键字太短'}), 400

    print(f"DEBUG: AMAP_SERVER_AK = {AMAP_SERVER_AK[:10]}...")

    from route_planner import RoutePlanner
    planner = RoutePlanner(AMAP_SERVER_AK)
    result = planner.inputtips(keywords)
    print(f"DEBUG: inputtips result = {result}")

    return jsonify(result)


@app.route('/api/route/plan', methods=['POST'])
def api_route_plan():
    """路径规划"""
    data = request.json
    segments = data.get('segments', [])

    if not segments:
        return jsonify({'status': 'error', 'error': '缺少路段信息'}), 400

    if len(segments) > 16:
        return jsonify({'status': 'error', 'error': '最多支持 16 个途经点'}), 400

    from route_planner import RoutePlanner
    planner = RoutePlanner(AMAP_SERVER_AK)
    result = planner.plan_route(segments)

    return jsonify(result)


@app.route('/api/directories')
def api_directories():
    """获取照片目录列表"""
    return jsonify(get_photo_dirs())


@app.route('/api/ai/generate-roadbook', methods=['POST'])
def api_ai_generate_roadbook():
    """AI 生成路书"""
    data = request.json

    # 验证必填字段
    required_fields = ['destination', 'travel_date_start', 'travel_date_end', 'people_count', 'car_type']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'status': 'error', 'error': f'缺少必填字段: {field}'}), 400

    # 检查 API Key
    if not DEEPSEEK_API_KEY:
        return jsonify({'status': 'error', 'error': 'DeepSeek API Key 未配置'}), 500

    try:
        # 动态导入 ai_generator（解决打包后导入问题）
        import importlib.util
        ai_path = os.path.join(CONFIG_BASE_DIR, 'ai_generator.py')
        ai_spec = importlib.util.spec_from_file_location("ai_generator", ai_path)
        ai_module = importlib.util.module_from_spec(ai_spec)
        ai_spec.loader.exec_module(ai_module)

        result = ai_module.generate_roadbook(
            user_input=data,
            api_key=DEEPSEEK_API_KEY,
            api_url=DEEPSEEK_API_URL,
            model=DEEPSEEK_MODEL
        )

        if result.get('status') == 'success':
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        import traceback
        return jsonify({'status': 'error', 'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/ai/generate-roadbook/stream', methods=['POST'])
def api_ai_generate_roadbook_stream():
    """流式 AI 生成路书"""
    import traceback
    import sys

    print("[DEBUG] api_ai_generate_roadbook_stream called", flush=True)
    try:
        data = request.json
        print(f"[DEBUG] request.json OK, data keys: {list(data.keys())}", flush=True)

        # 验证必填字段
        required_fields = ['destination', 'travel_date_start', 'travel_date_end', 'people_count', 'car_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'status': 'error', 'error': f'缺少必填字段: {field}'}), 400

        # 检查 API Key
        if not DEEPSEEK_API_KEY:
            print("[DEBUG] DEEPSEEK_API_KEY not configured", flush=True)
            return jsonify({'status': 'error', 'error': 'DeepSeek API Key 未配置'}), 500

        print(f"[DEBUG] DEEPSEEK_API_KEY configured: {DEEPSEEK_API_KEY[:4]}...", flush=True)
        print("[DEBUG] About to load ai_generator...", flush=True)
        # 动态导入 ai_generator（解决打包后导入问题）
        import importlib.util
        ai_path = os.path.join(CONFIG_BASE_DIR, 'ai_generator.py')
        print(f"[DEBUG] Loading ai_generator from: {ai_path}", flush=True)
        ai_spec = importlib.util.spec_from_file_location("ai_generator", ai_path)
        ai_module = importlib.util.module_from_spec(ai_spec)
        print(f"[DEBUG] Executing ai_generator module...", flush=True)
        ai_spec.loader.exec_module(ai_module)
        print(f"[DEBUG] ai_generator module loaded successfully", flush=True)

        generator = ai_module.RoadbookGenerator(
            api_key=DEEPSEEK_API_KEY,
            api_url=DEEPSEEK_API_URL,
            model=DEEPSEEK_MODEL
        )
        print("[DEBUG] RoadbookGenerator created", flush=True)

        def generate():
            print("[DEBUG] generate() started", flush=True)
            try:
                for chunk in generator.generate_stream(data):
                    yield chunk
            except Exception as e:
                import traceback
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"AI生成流错误: {e}\n{traceback.format_exc()}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        print("[DEBUG] About to return Response", flush=True)
        response = Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
        print("[DEBUG] Response object created", flush=True)
        return response
    except Exception as e:
        import traceback
        print(f"[ERROR] ai_generator stream exception: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        return jsonify({'status': 'error', 'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/weather')
def api_weather():
    """获取天气预报（使用高德天气 API）"""
    if not SHOW_WEATHER_INFO:
        return jsonify({'status': 'error', 'error': '天气功能已禁用'})

    location = request.args.get('location', '').strip()
    if not location:
        return jsonify({'status': 'error', 'error': '缺少城市参数'})

    if not AMAP_SERVER_AK:
        return jsonify({'status': 'error', 'error': '天气 API 未配置（请设置 AMAP_SERVER_AK）'})

    from weather import get_weather
    result = get_weather(location, AMAP_SERVER_AK)
    return jsonify(result)


@app.route('/api/outputs')
def api_outputs():
    """获取输出目录列表"""
    return jsonify(get_output_dirs())


@app.route('/api/save/roadbook', methods=['POST'])
def api_save_roadbook():
    """保存路书为 JSON 文件"""
    data = request.json
    roadbook_data = data.get('roadbook_data')
    filename = data.get('filename', 'roadbook.json')

    if not roadbook_data:
        return jsonify({'status': 'error', 'error': '缺少路书数据'}), 400

    try:
        import json as json_module

        # 生成文件路径
        save_dir = os.path.join(CONFIG_APP_DIR, 'output', 'roadbook')
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # 确保文件名安全
        safe_filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.', ' ', '(', ')'))
        file_path = os.path.join(save_dir, safe_filename)

        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json_module.dump(roadbook_data, f, ensure_ascii=False, indent=2)

        return jsonify({
            'status': 'success',
            'filename': safe_filename,
            'path': f'/output/roadbook/{safe_filename}',
            'full_url': f'http://localhost:{DESKTOP_PORT}/output/roadbook/{safe_filename}'
        })

    except Exception as e:
        import traceback
        return jsonify({'status': 'error', 'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/output/roadbook/<filename>')
def serve_roadbook(filename):
    """下载路书 JSON 文件"""
    save_dir = os.path.join(CONFIG_APP_DIR, 'output', 'roadbook')
    safe_path = os.path.join(save_dir, filename)

    if not os.path.exists(safe_path):
        abort(404)

    return send_file(safe_path, as_attachment=True, download_name=filename)


@app.route('/api/collections', methods=['GET'])
def get_collections():
    """获取收藏的路书列表"""
    collections_file = os.path.join(CONFIG_APP_DIR, 'collections.json')
    if os.path.exists(collections_file):
        with open(collections_file, 'r', encoding='utf-8') as f:
            return jsonify({'status': 'success', 'collections': json.load(f)})
    return jsonify({'status': 'success', 'collections': []})


@app.route('/api/collections', methods=['POST'])
def save_collections():
    """保存收藏的路书列表"""
    data = request.json
    collections = data.get('collections', [])
    collections_file = os.path.join(CONFIG_APP_DIR, 'collections.json')
    try:
        with open(collections_file, 'w', encoding='utf-8') as f:
            json.dump(collections, f, ensure_ascii=False, indent=2)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/export/excel', methods=['POST'])
def api_export_excel():
    """导出路书为 Excel 文件"""
    data = request.json
    roadbook_data = data.get('roadbook_data')

    if not roadbook_data:
        return jsonify({'status': 'error', 'error': '缺少路书数据'}), 400

    try:
        from excel_exporter import export_roadbook_to_excel, get_excel_filename

        # 生成临时文件路径
        excel_dir = os.path.join(CONFIG_APP_DIR, 'output', 'excel')
        if not os.path.exists(excel_dir):
            os.makedirs(excel_dir)

        filename = get_excel_filename(roadbook_data)
        excel_path = os.path.join(excel_dir, filename)

        # 导出 Excel
        export_roadbook_to_excel(roadbook_data, excel_path)

        return jsonify({
            'status': 'success',
            'filename': filename,
            'path': f'/output/excel/{filename}',
            'full_url': f'http://localhost:{DESKTOP_PORT}/output/excel/{filename}'
        })

    except Exception as e:
        import traceback
        return jsonify({'status': 'error', 'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/output/excel/<filename>')
def serve_excel(filename):
    """下载 Excel 文件"""
    excel_dir = os.path.join(CONFIG_APP_DIR, 'output', 'excel')
    safe_path = os.path.join(excel_dir, filename)

    if not os.path.exists(safe_path):
        abort(404)

    return send_file(safe_path, as_attachment=True, download_name=filename)


@app.route('/api/run', methods=['POST'])
def api_run():
    """执行 photo_track.py"""
    data = request.json

    photo_dir = data.get('photo_dir', '').strip()
    if not photo_dir:
        return jsonify({'error': '请选择或输入照片目录'}), 400

    # 验证目录是否存在
    photo_path = os.path.join(get_photo_base_dir(), photo_dir)
    if not os.path.exists(photo_path):
        return jsonify({'error': f'照片目录不存在: {photo_dir}'}), 400

    distance_threshold = data.get('distance_threshold', DISTANCE_THRESHOLD)
    time_threshold = data.get('time_threshold', TIME_THRESHOLD)
    html_only = data.get('html_only', False)

    # 创建任务
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': 'pending',
        'photo_dir': photo_dir,
        'output': [],
        'returncode': None,
        'output_dir': None
    }

    # 后台执行
    thread = threading.Thread(
        target=run_photo_track,
        args=(task_id, photo_dir, distance_threshold, time_threshold, html_only)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id})


@app.route('/api/status/<task_id>')
def api_status(task_id):
    """查询任务状态"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    return jsonify({
        'status': task['status'],
        'photo_dir': task.get('photo_dir'),
        'output': task.get('output', [])[-100:],  # 最近 100 行
        'returncode': task.get('returncode'),
        'output_dir': task.get('output_dir')
    })


@app.route('/output/<path:filename>')
def serve_output(filename):
    """访问生成的输出文件"""
    output_base = get_output_base_dir()
    safe_path = os.path.join(output_base, filename)
    print(f"serve_output: filename={filename}, output_base={output_base}, safe_path={safe_path}, exists={os.path.exists(safe_path)}")
    if not os.path.exists(safe_path):
        abort(404)

    # 直接发送文件，不再进行字符串替换和脚本注入
    # 生成的 HTML 文件中已包含正确的导航逻辑（使用 window.location.href）
    return send_file(safe_path)


if __name__ == '__main__':
    # 直接运行时启动服务器（Web 模式）
    import webbrowser
    import time

    photo_base = get_photo_base_dir()
    output_base = get_output_base_dir()
    print("=" * 50)
    print("RoadBook - Photo Track Generator")
    print("=" * 50)
    print(f"Photo folder: {photo_base}")
    print(f"Output folder: {output_base}")
    print()
    print("Starting server...")

    # 尝试启动服务器，如果端口被占用则尝试其他端口
    port = WEB_PORT
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            # 启动Flask服务器
            # 使用 threaded=True 支持多线程处理并发请求
            app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
            break
        except OSError as e:
            if port == WEB_PORT:
                print(f"Port {WEB_PORT} is in use, trying port {port + 1}...")
                port += 1
            else:
                print(f"Port {port} is in use, trying port {port + 1}...")
                port += 1
            if attempt == max_attempts - 1:
                print(f"ERROR: Could not find an available port (tried 5000-{port})")
                print("Please close other applications using these ports and try again.")
                input("Press Enter to exit...")
                sys.exit(1)

    # 延迟打开浏览器，等待服务器启动
    time.sleep(1.5)
    browser_url = f"http://localhost:{port}"
    print(f"Opening browser: {browser_url}")
    webbrowser.open(browser_url)
    print()
    print("=" * 50)
    print(f"Server running at: {browser_url}")
    print("Press Ctrl+C to stop server")
    print("=" * 50)
