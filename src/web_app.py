"""路书 RoadBook - Web 界面"""
import os
import sys
import json
import uuid
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file, abort

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


@app.route('/')
def index():
    """主页"""
    photo_dirs = get_photo_dirs()
    output_dirs = get_output_dirs()
    # Debug: 打印路径信息
    print(f"index: get_output_base_dir() = {get_output_base_dir()}")
    return render_template('config_template.html',
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


@app.route('/api/directories')
def api_directories():
    """获取照片目录列表"""
    return jsonify(get_photo_dirs())


@app.route('/api/outputs')
def api_outputs():
    """获取输出目录列表"""
    return jsonify(get_output_dirs())


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
