# 旅游路径规划功能开发计划

## Context

RoadBook 项目新增"旅游路径规划"功能，允许用户录入多个地点，选择每段路程的交通方式（驾车/步行/骑行/公交），系统调用高德路径规划 API 计算路线并在地图上展示。

**需求确认：**
- 地点录入：地名搜索 + 地图选点
- 交通方式：每两个相邻地点之间可单独选择交通方式（驾车/步行/骑行/公交）
- 功能入口：独立菜单页面

---

## 实现方案

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/route_planner.py` | 路径规划核心模块（新增） |
| `templates/route_template.html` | 路径规划页面（新增） |
| `static/route.css` | 页面样式（新增） |
| `static/route.js` | 前端交互逻辑（新增） |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `src/web_app.py` | 新增路由 `/route` 和 API 端点 |
| `templates/config_template.html` | 新增"路径规划"入口按钮 |

---

## 数据结构

### 请求：POST /api/route/plan
```json
{
    "segments": [
        {"from": {"name": "北京天安门", "lng": 116.397, "lat": 39.908}, "to": {"name": "天津意式风情区", "lng": 117.195, "lat": 39.153}, "strategy": "driving"},
        {"from": {"name": "天津意式风情区", "lng": 117.195, "lat": 39.153}, "to": {"name": "唐山抗震纪念碑", "lng": 118.180, "lat": 39.630}, "strategy": "walking"}
    ]
}
```

### 响应
```json
{
    "status": "success",
    "total_distance": 149500,
    "total_duration": 5940,
    "segments": [
        {
            "from": {...}, "to": {...}, "strategy": "driving",
            "distance": 120000, "duration": 4800,
            "path": [[lng, lat], ...],
            "steps": [{"instruction": "...", "distance": 500, "duration": 120}, ...]
        },
        {...}
    ]
}
```

---

## 核心模块

### route_planner.py

```python
class RoutePlanner:
    def plan_route(segments: List[Dict]) -> Dict:
        """
        segments: [{"from": {...}, "to": {...}, "strategy": "driving"}, ...]
        返回: {status, total_distance, total_duration, segments: [...]}
        """

    def geocode(address: str) -> Dict:
        """地理编码：地址转坐标"""
```

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/route` | GET | 路径规划页面 |
| `/api/route/geocode` | POST | 地理编码（地址→坐标） |
| `/api/route/plan` | POST | 执行路径规划 |

---

## UI 布局

```
+--------------------------------------------------+
|  RoadBook Logo                    [返回配置]     |
+--------------------------------------------------+
|                                                  |
|  地点列表                    地图                 |
|  +------------------------+ +-----------------+ |
|  | 1. 起始地: [输入框][搜索]| |                 | |
|  |    [驾车▼]              | |   高德地图       | |
|  |                        | |                 | |
|  | 2. 途经点: [输入框][搜索]| |   显示标记      | |
|  |    [步行▼]      [删除]  | |   显示路线      | |
|  |                        | |                 | |
|  | 3. 途经点: [输入框][搜索]| |                 | |
|  |    [骑行▼]      [删除]  | +-----------------+ |
|  |                        |                    |
|  | [+ 添加途经点]          | 路线概览           |
|  |                        | 总距离: 149.5 km   |
|  | 4. 目的地: [输入框][搜索]| 总时间: 约 1h40m   |
|  +------------------------+                    |
|                                                  |
|  [开始规划]                                      |
+--------------------------------------------------+
```

**每段交通方式下拉选项**：驾车 / 步行 / 骑行 / 公交

---

## 关键文件参考

| 用途 | 文件 |
|------|------|
| 高德 API 调用模式 | `src/geo_coder.py` |
| 地图 JS 交互 | `templates/map_template.html` |
| 配置和 Key 获取 | `src/config.py` |
| Flask 路由模式 | `src/web_app.py` |
| 前端 AJAX 模式 | `static/app.js` |

---

## 实现步骤

### Phase 1: 核心模块
1. 创建 `src/route_planner.py` - RoutePlanner 类
   - `geocode()` - 地理编码
   - `plan_segment()` - 单段路径规划
   - `plan_route()` - 多段路径规划

### Phase 2: Web 路由
2. 修改 `src/web_app.py`
   - `/route` 页面路由
   - `/api/route/geocode` 端点
   - `/api/route/plan` 端点

### Phase 3: 前端页面
3. 创建 `templates/route_template.html`
4. 创建 `static/route.css`
5. 创建 `static/route.js`

### Phase 4: 入口集成
6. 修改 `templates/config_template.html` 添加"路径规划"入口

---

## 验证方式

1. 启动 Web 应用: `python src/web_app.py`
2. 访问 `/route` 页面
3. 输入多个地点，搜索选择
4. 为每段选择交通方式
5. 点击"开始规划"，验证地图路线显示
6. 检查总距离/总时间计算