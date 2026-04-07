# 路书 — 技术规格

本文档是路书的**技术参考手册**，面向开发者。入门指南请参考 [README.md](README.md)。

---

## 1. 数据文件格式

### 1.1 文件列表

| 文件 | 说明 |
|------|------|
| `data_original.json` | 原始数据，每张照片一行，按时间排序 |
| `data_original_unknown.json` | 无 GPS 信息的照片列表 |
| `data_converted.json` | 治理后数据，相近坐标合并后的轨迹点列表 |

### 1.2 data_original.json 字段

```json
[{
    "uuid": "...",
    "latitude": 30.66321,
    "longitude": 104.04321,
    "altitude": 500,
    "timestamp": "2024-01-01T10:00:00",
    "filename": "IMG_001.jpg",
    "thumbnail_path": "thumbnail/xxx.jpg",
    "place_name": "锦里古街",
    "address": "武侯祠大街231号",
    "administrative": { "province": "四川省", "city": "成都市", "district": "武侯区" }
}]
```

### 1.3 data_converted.json 字段

```json
[{
    "latitude_tran": 30.66321,
    "longitude_tran": 104.04321,
    "place_name": "锦里古街",
    "address": "武侯祠大街231号",
    "administrative": { "province": "四川省", "city": "成都市", "district": "武侯区" },
    "day_segment": 1,
    "photo_count": 3,
    "photo_group": [
        { "uuid": "...", "latitude": 30.66321, "longitude": 104.04321, "timestamp": "2024-01-01T10:00:00", ... }
    ]
}]
```

### 1.4 字段对比

| 字段 | data_original | data_converted |
|------|--------------|----------------|
| 照片数量 | 每行1张 | 合并后1~N张 |
| 坐标 | 原始坐标 | 取组内第一张坐标 |
| day_segment | 无 | 根据时间间隔分段 |
| photo_group | 无 | 组内所有照片的详细信息数组 |

---

## 2. 数据治理流程

### 2.1 坐标合并 — `filter_nearby_points`

**触发条件**：相邻两点同时满足
- 距离 < 1000 米
- 时间差 < 7200 秒（2小时）

**合并逻辑**：
- 满足条件 → 归为同一组，保留所有照片
- 不满足条件 → 保存当前组，开启新组

**合并后字段**：`latitude_tran`、`longitude_tran`（取组内第一张）、`photo_count`、`day_segment`、`photo_group`

### 2.2 轨迹分段 — `segment_points_by_day`

**触发条件**：相邻两组时间间隔 > 4 小时

**分段逻辑**：
- 间隔 ≤ 4小时 → 同一 `day_segment`
- 间隔 > 4小时 → 新增 `day_segment`

### 2.3 颜色映射 — `DAY_COLORS`

每天轨迹使用不同颜色，10色循环。颜色在以下三处统一应用：
1. 地图上当天轨迹路线颜色
2. 左侧途经点 Label 圆圈颜色
3. 右侧行程列表序号圆圈背景色

---

## 3. photo_track.py 执行流程

### 3.1 主流程

```
1. collect_photo_points        → 扫描照片，提取 GPS、生成缩略图
2. resolve_place_names          → 逆地理编码（需 AMAP_SERVER_AK）
3. generate_original_json       → 生成 data_original.json
4. filter_nearby_points        → 坐标合并（距离<1000m 且 时间差<7200s）
5. segment_points_by_day        → 轨迹分段（间隔>4小时则新增 day_segment）
6. generate_converted_json      → 生成 data_converted.json
7. render_html_template         → 生成 track_output.html 和 timeline.html
```

支持 `-H`（`--html-only`）跳过前6步，直接加载已有 JSON 并重生成 HTML。

### 3.2 执行流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        main() 入口                              │
├─────────────────────────────────────────────────────────────────┤
│  1. 解析命令行参数 (photo_dir, -H, -d, -t)                      │
│  2. 构建路径：photo/{dir} 和 output/{dir}                       │
│  3. 检查是否为 -H 模式                                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
   ┌──────────────┐                ┌──────────────┐
   │ -H 模式?     │                │ 普通模式     │
   └──────┬───────┘                └──────┬───────┘
          │                               │
        是 │                             否
          │                               │
          ▼                               ▼
   ┌──────────────┐              ┌──────────────┐
   │ 加载已有     │              │ 删除output   │
   │ JSON文件     │              │ 文件夹内容   │
   └──────┬───────┘              └──────┬───────┘
          │                               │
          └─────────────┬─────────────────┘
                        ▼
   ┌──────────────────────────────────────────────────────────────┐
   │              collect_photo_points                             │
   │  - 遍历照片文件夹                                             │
   │  - 提取 GPS 坐标和生成缩略图                                  │
   └──────────────────────────┬───────────────────────────────────┘
                              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ resolve_place_names (逆地理编码，带 geocode_cache)            │
   └──────────────────────────┬───────────────────────────────────┘
                              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ generate_original_json → data_original.json                  │
   └──────────────────────────┬───────────────────────────────────┘
                              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ filter_nearby_points (距离 < 1000m 且 时间差 < 7200s)        │
   └──────────────────────────┬───────────────────────────────────┘
                              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ segment_points_by_day (间隔 > 4小时则新增 day_segment)        │
   └──────────────────────────┬───────────────────────────────────┘
                              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ generate_converted_json → data_converted.json                │
   └──────────────────────────┬───────────────────────────────────┘
                              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ render_html_template → track_output.html + timeline.html     │
   └───────────────────────────────────────────────────────────────┘
```

### 3.3 关键函数

| 阶段 | 函数 | 说明 |
|------|------|------|
| 照片处理 | `process_single_photo()` | 提取 GPS、生成缩略图 |
| 坐标合并 | `filter_nearby_points()` | 距离<1000m 且时间差<7200s |
| 轨迹分段 | `segment_points_by_day()` | 时间间隔>4小时则新段 |
| HTML 生成 | `render_html_template()` | Jinja2 模板渲染 |

---

## 4. 命令行

### 4.1 photo_track.py（轨迹生成）

```bash
python src/photo_track.py <photo_dir> [选项]
```

**命令规则：**

| 命令 | 行为 |
|------|------|
| `python src/photo_track.py <photo_dir>` | 删除 output 文件夹内容，全量重新处理所有照片 |
| `python src/photo_track.py <photo_dir> -H` | 仅生成 HTML，使用已有的 thumbnail 文件夹和 JSON 文件 |

**选项：**

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `-H, --html-only` | 跳过图片解析，仅生成 HTML | False |
| `-d, --distance-threshold` | 距离阈值（米），覆盖 config.py 配置 | 1000 |
| `-t, --time-threshold` | 时间阈值（秒），覆盖 config.py 配置 | 7200 |
| `-v, --verbose` | 显示详细日志 | False |

**示例：**

```bash
python src/photo_track.py test_photos
python src/photo_track.py test_photos -d 500 -t 1800
python src/photo_track.py test_photos -H
```

### 4.2 web_app.py（Web 界面）

```bash
python src/web_app.py
```

启动 Flask 服务器，打开浏览器访问 `http://localhost:{WEB_PORT}`（默认 18443）。

---

## 5. 关键模块说明

### 5.1 缓存系统 — `GeoCodeCache`

逆地理编码结果缓存，支持两种存储方式：

| 存储方式 | 配置 | 文件 |
|----------|------|------|
| JSON | `CACHE_TYPE = 'json'` | `cache/geocode_cache.json` |
| SQLite | `CACHE_TYPE = 'sqlite'` | `cache/cache.db` |

- 缓存键精度：小数点后5位（约1.1米）

### 5.2 Jinja2 模板变量

模板 `templates/map_template.html` 使用以下变量：

| 变量 | 说明 |
|------|------|
| `{{ amap_ak }}` | 高德 Web 端 Key（地图展示） |
| `{{ static_base }}` | 静态资源基础路径 |
| `{{ single_html }}` | 是否为单一 HTML 输出模式 |

---

## 6. API 路由

| 路由 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 主页面（配置页面） |
| `/api/directories` | GET | 获取照片目录列表 |
| `/api/outputs` | GET | 获取输出目录列表 |
| `/api/run` | POST | 执行 photo_track.py |
| `/api/status/<task_id>` | GET | 查询任务状态（轮询） |
| `/output/<path>` | GET | 访问生成的输出文件 |

---

## 7. 桌面端调试

### 7.1 PyInstaller 配置（roadbook.spec）

| 配置项 | 说明 |
|--------|------|
| `console=True/False` | 是否显示控制台窗口 |

### 7.2 PyWebView 调试模式（desktop_app.py）

```python
webview.start(main, window, debug=False)
```

| 参数 | 说明 |
|------|------|
| `debug=False` | 关闭 PyWebView 内置开发者工具 |
| `debug=True` | 开启 PyWebView 内置开发者工具 |
