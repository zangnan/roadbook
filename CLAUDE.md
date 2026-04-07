# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

路书 RoadBook — 将旅行照片转化为交互式轨迹地图的工具。从照片 EXIF 信息中提取 GPS 坐标，自动生成可交互的轨迹地图和时间轴页面。

- Python 3.11+
- Windows 桌面应用 (PyWebView) + 浏览器访问
- 依赖高德地图 API

## 常用命令

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行应用
```bash
# Web 应用
python src/web_app.py
# 访问 http://localhost:18443

# CLI 轨迹生成
python src/photo_track.py <photo_dir> [选项]
```

### CLI 选项
| 选项 | 说明 | 默认值 |
|------|------|--------|
| `-H, --html-only` | 跳过图片解析，仅生成 HTML | False |
| `-d, --distance-threshold` | 距离阈值（米） | 1000 |
| `-t, --time-threshold` | 时间阈值（秒） | 7200 |
| `-v, --verbose` | 详细日志 | False |

### 打包
```bash
build.bat
```
输出: `dist/roadbook.exe`

## 架构

### 数据流程
```
照片 → EXIF GPS 提取 → 逆地理编码(缓存) → 坐标合并 → 轨迹分段 → HTML 生成
```

### 核心模块 (src/)
| 文件 | 职责 |
|------|------|
| `photo_track.py` | CLI 入口，主流程编排 |
| `track_generator.py` | 轨迹处理核心逻辑：坐标合并、轨迹分段、模板渲染 |
| `exif_reader.py` | 读取照片 EXIF GPS 信息 |
| `coord_converter.py` | WGS84→GCJ02 坐标转换、Haversine 距离计算 |
| `thumbnail.py` | 缩略图和原图压缩生成 |
| `geo_coder.py` | 高德逆地理编码 + SQLite/JSON 缓存 |
| `web_app.py` | Flask Web 应用入口 |
| `desktop_app.py` | PyWebView 桌面应用入口 |
| `config.py` | 配置管理，支持打包后运行 |

### 模板 (templates/)
| 文件 | 用途 |
|------|------|
| `map_template.html` | 轨迹地图页面 |
| `timeline_template.html` | 时间轴页面 |
| `config_template.html` | 配置页面 |

### 关键算法
- **坐标合并**: `filter_nearby_points` — 距离<1000m 且 时间差<7200s 的相邻点合并为一组
- **轨迹分段**: `segment_points_by_day` — 相邻组时间间隔>4小时则新增 day_segment
- **颜色映射**: `DAY_COLORS` 数组，每天轨迹使用不同颜色（10色循环）

### 输出文件
```
output/{photo_dir}/
├── data_original.json          # 原始数据
├── data_converted.json         # 治理后数据
├── data_original_unknown.json  # 无 GPS 照片
├── thumbnail/                   # 缩略图和原图
├── track_output.html           # 轨迹地图
└── timeline.html               # 时间轴
```

### 配置 (.env)
需配置高德地图 API Key 才能使用地理编码功能：
- `AMAP_WEB_AK` — 地图展示
- `AMAP_SERVER_AK` — 逆地理编码

## PyInstaller 打包注意事项

- `roadbook.spec` 配置了 `console=False`（无控制台窗口）
- 打包后 `sys._MEIPASS` 为临时资源目录，`sys.executable` 所在目录为数据目录
- `config.py` 处理了打包/开发环境的路径差异
