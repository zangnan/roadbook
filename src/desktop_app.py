"""路书 RoadBook - PyWebView 桌面应用"""
import os
import sys
import threading
import importlib.util

# 打包后运行
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # desktop_app.py 在 src/ 目录下时，APP_DIR 应该是项目根目录
    if os.path.basename(BASE_DIR) == 'src':
        APP_DIR = os.path.dirname(BASE_DIR)
    else:
        APP_DIR = BASE_DIR

sys.path.insert(0, BASE_DIR)

# 加载 config
if getattr(sys, 'frozen', False):
    # frozen 模式：datas 中的 'src/config.py' 被提取到 BASE_DIR
    config_path = os.path.join(BASE_DIR, 'config.py')
else:
    # 开发模式：config.py 在 src/ 目录下
    config_path = os.path.join(BASE_DIR, 'src', 'config.py')
config_spec = importlib.util.spec_from_file_location("config", config_path)
config = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(config)

DESKTOP_PORT = config.DESKTOP_PORT

# 确保运行时目录存在
for dir_name in ['photo', 'output', 'cache']:
    dir_path = os.path.join(APP_DIR, dir_name)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def start_flask_server(port, app):
    """启动 Flask 服务器"""
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True, use_reloader=False)


def main(window):
    """主函数，由 webview.start 调用"""
    # 获取服务器端口
    port = DESKTOP_PORT

    # 暴露导航函数给 JavaScript
    def navigate(url):
        # 如果是相对路径，转换为完整 URL
        if url.startswith('/'):
            url = f'http://localhost:{port}{url}'
        print(f'Navigating to: {url}')
        window.load_url(url)

    window.expose(navigate)

    print("PyWebView API exposed: navigate")


if __name__ == '__main__':
    import webview

    # 动态导入 web_app（使用 importlib 以兼容 PyInstaller 打包）
    import importlib.util
    web_app_path = os.path.join(BASE_DIR, 'web_app.py')
    spec = importlib.util.spec_from_file_location("web_app", web_app_path)
    web_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(web_app)

    app = web_app.app
    photo_base = web_app.get_photo_base_dir()
    output_base = web_app.get_output_base_dir()

    # 启动 Flask 服务器
    port = DESKTOP_PORT
    server_thread = threading.Thread(target=start_flask_server, args=(port, app), daemon=True)
    server_thread.start()

    print("=" * 50)
    print("RoadBook - Photo Track Generator")
    print("=" * 50)
    print(f"Photo folder: {photo_base}")
    print(f"Output folder: {output_base}")
    print(f"Server: http://localhost:{port}")
    print()
    print("Opening desktop window...")

    # 创建 PyWebView 窗口
    window = webview.create_window(
        title='路书 RoadBook',
        url=f'http://localhost:{port}?desktop=1',
        width=1280,
        height=800,
        min_size=(800, 600),
        resizable=True
    )

    # 启动 PyWebView
    webview.start(main, window, debug=False)

    print()
    print("Application closed.")
    sys.exit(0)
