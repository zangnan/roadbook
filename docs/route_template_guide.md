# 路书JSON模板填充说明

## 文件位置
- JSON Schema: `templates/route_template.json`
- 示例数据: `docs/route.md`

---

## 快速开始

### 1. basic_info - 基本信息

| 字段 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `title` | string | 否 | 路书标题 | "大连出发・8天草原环线自驾" |
| `travel_date` | string | 是 | 出行时间（MM.DD-MM.DD） | "7.15-7.22" |
| `days` | integer | 是 | 总天数 | 8 |
| `car_type` | string | 是 | 车型 | "轿车" |
| `people_count` | integer | 是 | 人数 | 5 |
| `room_count` | integer | 否 | 房间数 | 2 |
| `total_distance_km` | number | 是 | 全程里程 | 2800 |
| `fuel_consumption` | string | 否 | 油耗 | "6.5L/100km" |
| `elevation_range` | string | 否 | 海拔范围 | "20-1400m" |
| `high_altitude_warning` | boolean | 否 | 高反风险 | false |
| `route_summary` | string | 否 | 路线概要 | "大连→通辽→...→大连" |

### 2. daily_itinerary - 每日行程（数组）

每天是一个对象，字段说明：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `day_number` | integer | 是 | 第几天（从1开始） |
| `date` | string | 是 | 日期（MM.DD格式） |
| `origin` | string | 是 | 出发地 |
| `destination` | string | 是 | 目的地 |
| `distance_km` | number | 是 | 当日里程（公里） |
| `duration_hours` | number | 是 | 车程（小时） |
| `elevation_m` | string | 是 | 海拔（格式：min-max） |
| `route` | string | 否 | 途经路线 |
| `highlights` | array | 否 | 景点列表（字符串数组） |
| `accommodation` | object | 否 | 住宿信息 |
| `food` | array | 否 | 推荐美食 |
| `tips` | array | 否 | 避坑提示 |
| `gas_station` | string | 否 | 加油地点 |
| `notes` | string | 否 | 其他备注 |

**accommodation 对象结构：**
```json
{
  "location": "通辽市区",
  "type": "连锁酒店",
  "price_per_room": 280
}
```

### 3. budget - 费用明细

| 字段 | 类型 | 说明 |
|------|------|------|
| `transportation` | object | 交通费用 |
| `accommodation` | object | 住宿费用 |
| `food` | object | 餐饮费用 |
| `tickets_and_misc` | object | 门票杂费 |
| `grand_total` | object | 总计 |

**transportation 子字段：**
| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `fuel_total_liters` | number | 总油耗（升） | 182 |
| `fuel_cost` | number | 油费（元） | 1456 |
| `toll_fees` | number | 过路费（元） | 890 |
| `transportation_total` | number | 交通合计（元） | 2346 |
| `per_person` | number | 人均交通费（元） | 469 |

> 计算公式：油费 = 总油耗 × 单价；交通合计 = 油费 + 过路费

**accommodation 子字段：**
| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `nights` | integer | 住宿晚数 | 7 |
| `rooms` | integer | 房间数量 | 2 |
| `total` | number | 住宿合计（元）= 每晚房价 × 房间数 × 晚数 | 4500 |
| `per_person` | number | 人均住宿费（元）= 住宿合计 ÷ 人数 | 900 |

> 计算公式：total = 每晚房价 × rooms × nights；per_person = total ÷ 人数

**food 子字段：**
| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `daily_budget_per_person` | number | 人均日餐饮预算（元） | 200 |
| `days` | integer | 天数 | 8 |
| `per_person` | number | 人均餐饮总计（元） | 1600 |
| `group_total` | number | 团队餐饮总计（元） | 8000 |

> 计算公式：per_person = daily_budget_per_person × days；group_total = per_person × 人数

**tickets_and_misc 子字段：**
| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `items` | string | 费用明细说明 | "九曲湾50+布林泉30+..." |
| `per_person` | number | 人均（元） | 300 |
| `group_total` | number | 团队总计（元） | 1500 |

**grand_total 子字段：**
| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `per_person` | number | 人均总费用（元） | 2819 |
| `group_total` | number | 团队总费用（元） | 14096 |

> 计算公式：per_person = 交通per_person + 住宿per_person + 餐饮per_person + 门票per_person

### 4. checklist - 出行必备提醒

数组格式，每项包含 category（分类）和 items（具体事项数组）：

```json
[
  {
    "category": "导航",
    "items": ["提前下载离线地图"]
  },
  {
    "category": "加油",
    "items": ["城镇见油就补", "草原深处无加油站"]
  }
]
```

---

## 完整示例

```json
{
  "basic_info": {
    "title": "大连出发・8天草原环线自驾",
    "travel_date": "7.15-7.22",
    "days": 8,
    "car_type": "轿车",
    "people_count": 5,
    "room_count": 2,
    "total_distance_km": 2800,
    "fuel_consumption": "6.5L/100km",
    "elevation_range": "20-1400m",
    "high_altitude_warning": false,
    "route_summary": "大连→通辽→霍林郭勒→乌拉盖→锡林浩特→经棚→热水塘→赤峰→大连"
  },
  "daily_itinerary": [
    {
      "day_number": 1,
      "date": "7.15",
      "origin": "大连",
      "destination": "通辽",
      "distance_km": 580,
      "duration_hours": 6.5,
      "elevation_m": "20-190",
      "route": "沈海高速→阜营高速→新鲁高速",
      "highlights": ["科尔沁博物馆", "大青沟"],
      "accommodation": {
        "location": "通辽市区",
        "type": "连锁酒店",
        "price_per_room": 280
      },
      "food": ["蒙式奶茶", "手把肉", "东北锅包肉"],
      "tips": ["大青沟骑马漂流先问价", "高速口特产慎买"],
      "gas_station": "通辽市区加满"
    }
  ],
  "budget": {
    "transportation": {
      "fuel_total_liters": 182,
      "fuel_cost": 1456,
      "toll_fees": 890,
      "transportation_total": 2346,
      "per_person": 469
    },
    "accommodation": {
      "nights": 7,
      "total": 2250,
      "per_person": 450
    },
    "food": {
      "daily_budget_per_person": 200,
      "days": 8,
      "per_person": 1600,
      "group_total": 8000
    },
    "tickets_and_misc": {
      "items": "九曲湾50+布林泉30+达里湖120+停车应急等",
      "per_person": 300,
      "group_total": 1500
    },
    "grand_total": {
      "per_person": 2819,
      "group_total": 14096
    }
  },
  "checklist": [
    {
      "category": "导航",
      "items": ["提前下载通辽、锡林郭勒、赤峰离线地图"]
    },
    {
      "category": "加油",
      "items": ["城镇见油就补", "草原深处无加油站"]
    }
  ]
}
```

---

## AI 填充提示词

当需要AI生成路书时，可使用以下提示词：

```
请基于以下信息生成标准JSON格式的路书数据：
- 目的地：
- 出发日期：
- 天数：
- 人数/房数：
- 车型：
- 预算偏好：
- 特殊需求：

请严格按照 templates/route_template.json 的格式输出JSON。
```
