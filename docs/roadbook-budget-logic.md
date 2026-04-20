# 路书预算计算逻辑

## 背景

AI 生成的路书中，费用相关字段（油耗、油费、过路费、交通合计、住宿小计、餐饮合计、门票合计、杂费合计、人均总计、团队总计）均由 AI 计算写入 JSON。由于 AI 经常算错，导致显示的预算数据错误。

**解决方案**：AI 只提供基础数据（里程、油耗、油价、各类单价/数量/费率），所有计算由程序完成。

---

## 一、数据结构

### 1.1 basic_info（AI 提供）

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `title` | string | AI | 路书标题 |
| `travel_date_start` | string | AI | 出发日期 yyyy-MM-dd |
| `travel_date_end` | string | AI | 返回日期 yyyy-MM-dd |
| `days` | int | AI | 天数 |
| `car_type` | string | AI | 车型 |
| `people_count` | int | AI | 人数 |
| `room_count` | int | AI | 房间数 |
| `total_distance_km` | float | AI 或程序汇总 | 总里程 km |
| `fuel_consumption` | string | AI | 油耗，如 "7.5L/100km" |
| `fuel_price` | float | AI | 油价（元/升） |
| `elevation_range` | string | AI | 海拔范围 |
| `high_altitude_warning` | bool | AI | 高原警告 |
| `route_summary` | string | AI | 路线概要 |

### 1.2 daily_itinerary（AI 提供，程序汇总）

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `day_number` | int | AI | 第几天 |
| `date` | string | AI | 日期 yyyy-MM-dd |
| `origin` | string | AI | 出发地 |
| `destination` | string | AI | 目的地 |
| `distance_km` | float | AI | 当日里程 km |
| `duration_hours` | float | AI | 车程小时 |
| `elevation_m` | string | AI | 海拔范围 |
| `route` | string | AI | 途经道路 |
| `route_stops` | array | AI | 行程节点 |
| `highlights` | array | AI | 途经景点 |
| `accommodation` | string | AI | 住宿地点（名称） |
| `food` | array | AI | 美食推荐 |
| `tips` | array | AI | 出行提示 |
| `gas_station` | string | AI | 加油站说明 |

**程序汇总**：`basic_info.total_distance_km = Σ(daily_itinerary[].distance_km)`

### 1.3 budget（程序计算，AI 只提供原始输入值）

#### transportation

| 字段 | AI 写入 | 程序计算 | 说明 |
|------|---------|---------|------|
| `car_type` | √ | — | 车型（从 basic_info 同步） |
| `fuel_total_liters` | 0占位 | √ | 总油耗 = totalDist × fuelConsNum ÷ 100 |
| `fuel_cost` | 0占位 | √ | 油费 = fuelTotalLiters × fuelPrice |
| `toll_fees` | √ 估算 | — | 过路费（用户可编辑） |
| `transportation_total` | 0占位 | √ | 交通合计 = fuelCost + tollFees |
| `per_person` | 0占位 | √ | 人均交通 = transportationTotal ÷ people |

#### accommodation

| 字段 | AI 写入 | 程序计算 | 说明 |
|------|---------|---------|------|
| `location` | √ | — | 住宿地点 |
| `type` | √ | — | 酒店类型 |
| `price_per_room` | √ | — | 每间房价 |
| `nights` | √ | — | 晚数 |
| `rooms` | √ | — | 房间数 |

程序汇总：住宿合计 = Σ(price_per_room × nights × rooms)

#### food

| 字段 | AI 写入 | 程序计算 | 说明 |
|------|---------|---------|------|
| `daily_budget_per_person` | √ | — | 人均日餐饮预算 |
| `days` | — | √ | 从 basic_info.days 读取 |
| `per_person` | 0占位 | √ | 人均餐饮 = dailyBudget × days |
| `group_total` | 0占位 | √ | 团队餐饮 = per_person × people |

#### tickets

| 字段 | AI 写入 | 程序计算 | 说明 |
|------|---------|---------|------|
| `item` | √ | — | 景点名 |
| `total` | √ | — | 金额 |
| `remark` | √ | — | 备注 |

程序汇总：门票合计 = Σ(tickets[].total)

#### misc

| 字段 | AI 写入 | 程序计算 | 说明 |
|------|---------|---------|------|
| `item` | √ | — | 杂费项 |
| `total` | √ | — | 金额 |

程序汇总：杂费合计 = Σ(misc[].total)

#### grand_total

| 字段 | AI 写入 | 程序计算 | 说明 |
|------|---------|---------|------|
| `per_person` | 0占位 | √ | per_person 之和 |
| `group_total` | 0占位 | √ | per_person × people |

---

## 二、计算公式

### 2.1 交通费用

```
fuelConsNum = parseFloat(fuel_consumption)  // 从 "7.5L/100km" 提取 7.5
fuelTotalLiters = total_distance_km × fuelConsNum ÷ 100
fuelCost = fuelTotalLiters × fuel_price
transportationTotal = fuelCost + toll_fees
transportationPerPerson = transportationTotal ÷ people
```

### 2.2 住宿费用

```
accommodationTotal = Σ(price_per_room × nights × rooms)
accommodationPerPerson = accommodationTotal ÷ people
```

### 2.3 餐饮费用

```
foodPerPerson = daily_budget_per_person × days
foodGroupTotal = foodPerPerson × people
```

### 2.4 门票/杂费

```
ticketsTotal = Σ(tickets[].total)
miscTotal = Σ(misc[].total)
```

### 2.5 总费用

```
ticketsPerPerson = ticketsTotal ÷ people
miscPerPerson = miscTotal ÷ people
perPersonTotal = transportationPerPerson + accommodationPerPerson + foodPerPerson + ticketsPerPerson + miscPerPerson
groupTotal = perPersonTotal × people
```

---

## 三、触发时机

1. **加载 JSON 后**：`loadRoadbook()` → `recalculateBudget()` → 重算所有费用
2. **预算编辑器保存后**：`saveBudgetEditor()` → 立即重算所有费用
3. **编辑每日行程里程变化后**：重新汇总 total_distance_km 并重算

---

## 四、涉及文件

| 文件 | 修改内容 |
|------|---------|
| `src/ai_generator.py` | ROUTE_SCHEMA_TEMPLATE 中预算字段改为 0 占位，SYSTEM_PROMPT 增加计算规则说明 |
| `templates/roadbook_template.html` | `recalculateBudget()` 重写为完整计算函数；`loadRoadbook()` 加载后调用；`saveBudgetEditor()` 保存后调用 |

---

## 五、关键函数设计

### recalculateBudget()

```javascript
function recalculateBudget() {
    const info = currentRoadbook.basic_info;
    const people = info.people_count || 1;
    const days = info.days || 1;
    const totalDist = info.total_distance_km || 0;
    const carType = info.car_type || '';

    // 油耗：从 "7.5L/100km" 提取数字
    const fuelConsRaw = info.fuel_consumption || '0';
    const fuelConsNum = parseFloat(fuelConsRaw) || 8;
    const fuelPrice = info.fuel_price || 8;

    // 交通费用
    const fuelTotalLiters = totalDist * fuelConsNum / 100;
    const tollFees = currentRoadbook.budget?.transportation?.toll_fees || 0;
    const fuelCost = Math.round(fuelTotalLiters * fuelPrice);
    const transportationTotal = fuelCost + tollFees;
    const transportationPerPerson = Math.round(transportationTotal / people);

    // 住宿费用
    let accommodationTotal = 0;
    (currentRoadbook.budget.accommodation || []).forEach(acc => {
        accommodationTotal += (acc.price_per_room || 0) * (acc.nights || 1) * (acc.rooms || 1);
    });
    const accommodationPerPerson = Math.round(accommodationTotal / people);

    // 餐饮费用
    const dailyFoodBudget = currentRoadbook.budget?.food?.daily_budget_per_person || 200;
    const foodPerPerson = dailyFoodBudget * days;
    const foodGroupTotal = foodPerPerson * people;

    // 门票/杂费
    let ticketsTotal = 0;
    (currentRoadbook.budget.tickets || []).forEach(t => { ticketsTotal += t.total || 0; });
    let miscTotal = 0;
    (currentRoadbook.budget.misc || []).forEach(m => { miscTotal += m.total || 0; });
    const ticketsPerPerson = Math.round(ticketsTotal / people);
    const miscPerPerson = Math.round(miscTotal / people);

    // 总费用
    const perPersonTotal = transportationPerPerson + accommodationPerPerson + foodPerPerson + ticketsPerPerson + miscPerPerson;
    const groupTotal = perPersonTotal * people;

    // 写回 budget
    currentRoadbook.budget.transportation = {
        car_type: carType,
        fuel_total_liters: Math.round(fuelTotalLiters * 10) / 10,
        fuel_cost: fuelCost,
        toll_fees: tollFees,
        transportation_total: transportationTotal,
        per_person: transportationPerPerson
    };
    currentRoadbook.budget.food = {
        ...(currentRoadbook.budget.food || {}),
        per_person: foodPerPerson,
        group_total: foodGroupTotal
    };
    currentRoadbook.budget.grand_total = {
        per_person: perPersonTotal,
        group_total: groupTotal
    };
}
```
