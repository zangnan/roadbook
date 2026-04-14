# 路书编辑功能详细实现方案

## Context
路书模板已完成本地保存和天气集成功能，现在需要实现最后一个主要功能：路书编辑。让用户可以手动修改 AI 生成的路书数据。

---

## 1. 功能设计

### 编辑范围
| 模块 | 可编辑字段 | 编辑方式 |
|------|-----------|---------|
| 基本信息 | title, travel_date, days, people_count, room_count, car_type, total_distance_km | 模态框 |
| 每日行程 | date, origin, destination, distance_km, duration_hours, highlights, accommodation, food, tips | 模态框 |
| 出行清单 | items（新增/删除/勾选） | 行内编辑 |

### 不直接编辑的字段（需重新计算）
- 预算相关（由基本信息重新计算）
- 天气数据（自动获取）

---

## 2. UI 设计

### 2.1 编辑入口
在每个 section 的标题栏添加"编辑"按钮：
```html
<div class="section-header">
    <div class="section-title">基本信息</div>
    <button class="section-edit-btn" onclick="openBasicInfoEditor()">
        ✏️ 编辑
    </button>
</div>
```

### 2.2 模态框编辑（基本信息 + 每日行程）
```
┌─────────────────────────────────────────┐
│ 编辑路书                            [×] │
├─────────────────────────────────────────┤
│ 标题：_____________________________     │
│ 出行日期：[___________] 天数：[__]      │
│ 人数：[__]  房间：[__]  车型：[SUV▼]   │
│ 总里程：____________km                  │
├─────────────────────────────────────────┤
│ 途经景点（逗号分隔）：                    │
│ [________________________________]     │
├─────────────────────────────────────────┤
│          [取消]      [保存]              │
└─────────────────────────────────────────┘
```

### 2.3 每日行程编辑器
每个 day-card 添加"编辑"按钮，点击后弹出模态框编辑当天行程。

---

## 3. 技术实现

### 3.1 编辑状态管理
```javascript
let editState = {
    active: false,
    type: null, // 'basic' | 'daily' | 'checklist'
    index: null // day index when editing daily
};
```

### 3.2 模态框 HTML (在 body 末尾添加)
```html
<div class="editor-modal" id="editorModal">
    <div class="editor-content">
        <div class="editor-header">
            <span class="editor-title">编辑</span>
            <button class="editor-close" onclick="closeEditor()">×</button>
        </div>
        <div class="editor-body" id="editorBody">
            <!-- 动态内容 -->
        </div>
        <div class="editor-footer">
            <button class="btn btn-secondary" onclick="closeEditor()">取消</button>
            <button class="btn btn-primary" onclick="saveEditor()">保存</button>
        </div>
    </div>
</div>
```

### 3.3 编辑表单生成函数

#### 基本信息编辑器
```javascript
function openBasicInfoEditor() {
    const info = currentRoadbook.basic_info;
    document.getElementById('editorTitle').textContent = '编辑基本信息';

    document.getElementById('editorBody').innerHTML = `
        <div class="form-group">
            <label>标题</label>
            <input type="text" id="edit-title" value="${info.title || ''}">
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>出行日期</label>
                <input type="date" id="edit-travel_date" value="${info.travel_date || ''}">
            </div>
            <div class="form-group">
                <label>天数</label>
                <input type="number" id="edit-days" value="${info.days || 1}" min="1">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>人数</label>
                <input type="number" id="edit-people_count" value="${info.people_count || 1}" min="1">
            </div>
            <div class="form-group">
                <label>房数</label>
                <input type="number" id="edit-room_count" value="${info.room_count || 1}" min="1">
            </div>
            <div class="form-group">
                <label>车型</label>
                <select id="edit-car_type">
                    <option value="轿车">轿车</option>
                    <option value="SUV" ${info.car_type === 'SUV' ? 'selected' : ''}>SUV</option>
                    <option value="越野车">越野车</option>
                    <option value="MVP">MVP</option>
                </select>
            </div>
        </div>
        <div class="form-group">
            <label>总里程 (km)</label>
            <input type="number" id="edit-total_distance_km" value="${info.total_distance_km || 0}">
        </div>
    `;

    editState = { active: true, type: 'basic', index: null };
    document.getElementById('editorModal').classList.add('active');
}
```

#### 每日行程编辑器
```javascript
function openDailyEditor(dayIndex) {
    const day = currentRoadbook.daily_itinerary[dayIndex];
    document.getElementById('editorTitle').textContent = `编辑第${day.day_number}天行程`;

    document.getElementById('editorBody').innerHTML = `
        <div class="form-row">
            <div class="form-group">
                <label>日期</label>
                <input type="date" id="edit-date" value="${day.date || ''}">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>出发地</label>
                <input type="text" id="edit-origin" value="${day.origin || ''}">
            </div>
            <div class="form-group">
                <label>目的地</label>
                <input type="text" id="edit-destination" value="${day.destination || ''}">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>里程 (km)</label>
                <input type="number" id="edit-distance_km" value="${day.distance_km || 0}">
            </div>
            <div class="form-group">
                <label>车程 (h)</label>
                <input type="number" id="edit-duration_hours" value="${day.duration_hours || 0}" step="0.5">
            </div>
        </div>
        <div class="form-group">
            <label>途经道路</label>
            <input type="text" id="edit-route" value="${day.route || ''}">
        </div>
        <div class="form-group">
            <label>途经景点（逗号分隔）</label>
            <input type="text" id="edit-highlights" value="${(day.highlights || []).join('，')}">
        </div>
        <div class="form-group">
            <label>住宿地点</label>
            <input type="text" id="edit-accommodation_location" value="${day.accommodation?.location || ''}">
        </div>
        <div class="form-group">
            <label>住宿类型</label>
            <input type="text" id="edit-accommodation_type" value="${day.accommodation?.type || ''}">
        </div>
        <div class="form-group">
            <label>住宿价格/间</label>
            <input type="number" id="edit-accommodation_price" value="${day.accommodation?.price_per_room || ''}">
        </div>
        <div class="form-group">
            <label>美食推荐（逗号分隔）</label>
            <input type="text" id="edit-food" value="${(day.food || []).join('，')}">
        </div>
        <div class="form-group">
            <label>出行提示（逗号分隔）</label>
            <input type="text" id="edit-tips" value="${(day.tips || []).join('；')}">
        </div>
    `;

    editState = { active: true, type: 'daily', index: dayIndex };
    document.getElementById('editorModal').classList.add('active');
}
```

### 3.4 保存编辑函数
```javascript
function saveEditor() {
    if (editState.type === 'basic') {
        // 收集表单数据
        currentRoadbook.basic_info = {
            ...currentRoadbook.basic_info,
            title: document.getElementById('edit-title').value,
            travel_date: document.getElementById('edit-travel_date').value,
            days: parseInt(document.getElementById('edit-days').value),
            people_count: parseInt(document.getElementById('edit-people_count').value),
            room_count: parseInt(document.getElementById('edit-room_count').value),
            car_type: document.getElementById('edit-car_type').value,
            total_distance_km: parseFloat(document.getElementById('edit-total_distance_km').value)
        };

        // 重新计算预算（简单估算）
        recalculateBudget();

        // 重新渲染
        displayBasicInfo(currentRoadbook.basic_info, currentRoadbook.budget);
        displayRouteSummary(currentRoadbook.basic_info);

    } else if (editState.type === 'daily') {
        const dayIndex = editState.index;
        const day = currentRoadbook.daily_itinerary[dayIndex];

        day.date = document.getElementById('edit-date').value;
        day.origin = document.getElementById('edit-origin').value;
        day.destination = document.getElementById('edit-destination').value;
        day.distance_km = parseFloat(document.getElementById('edit-distance_km').value) || 0;
        day.duration_hours = parseFloat(document.getElementById('edit-duration_hours').value) || 0;
        day.route = document.getElementById('edit-route').value;

        // 解析逗号分隔的数组
        day.highlights = document.getElementById('edit-highlights').value
            .split(/[,，]/)
            .map(s => s.trim())
            .filter(s => s);

        day.accommodation = {
            location: document.getElementById('edit-accommodation_location').value,
            type: document.getElementById('edit-accommodation_type').value,
            price_per_room: parseInt(document.getElementById('edit-accommodation_price').value) || 0
        };

        day.food = document.getElementById('edit-food').value
            .split(/[,，]/)
            .map(s => s.trim())
            .filter(s => s);

        day.tips = document.getElementById('edit-tips').value
            .split(/[;；]/)
            .map(s => s.trim())
            .filter(s => s);

        // 重新获取天气
        if (day.destination) {
            fetchDayWeather(day.day_number, day.destination);
        }

        // 重新渲染
        displayDailyItinerary(currentRoadbook.daily_itinerary);

        // 重新计算总里程
        recalculateTotalDistance();
    }

    closeEditor();
}

function closeEditor() {
    editState = { active: false, type: null, index: null };
    document.getElementById('editorModal').classList.remove('active');
}
```

### 3.5 辅助函数
```javascript
function recalculateBudget() {
    const info = currentRoadbook.basic_info;
    const days = info.days || 1;
    const people = info.people_count || 1;
    const rooms = info.room_count || 1;

    // 简化的预算重算逻辑
    // 实际应该根据修改后的数据重新计算
    if (currentRoadbook.budget) {
        currentRoadbook.budget.grand_total = {
            per_person: Math.round(currentRoadbook.budget.transportation.per_person +
                currentRoadbook.budget.accommodation.per_person +
                currentRoadbook.budget.food.per_person +
                currentRoadbook.budget.tickets_and_misc.per_person),
            group_total: 0
        };
        currentRoadbook.budget.grand_total.group_total =
            currentRoadbook.budget.grand_total.per_person * people;
    }

    displayBudget(currentRoadbook.budget);
}

function recalculateTotalDistance() {
    const total = currentRoadbook.daily_itinerary.reduce((sum, day) => {
        return sum + (day.distance_km || 0);
    }, 0);
    currentRoadbook.basic_info.total_distance_km = total;
    document.querySelector('.basic-info-card:nth-child(3) .basic-info-card-value').textContent = total + 'km';
}
```

### 3.6 在 day-card 添加编辑按钮
在 `displayDailyItinerary` 函数中，每个 day-header 添加编辑按钮：
```javascript
<div class="day-header">
    <div class="day-header-left">
        <span class="day-badge">第${day.day_number}天</span>
        <span class="day-date">${day.date}</span>
    </div>
    <div class="day-route-inline">
        ...
    </div>
    <div class="day-header-right">
        <button class="day-edit-btn" onclick="event.stopPropagation(); openDailyEditor(${index})">✏️</button>
        ...
    </div>
</div>
```

---

## 4. CSS 样式

```css
/* 编辑按钮 */
.section-edit-btn {
    padding: 4px 10px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--bg-glass);
    color: var(--text-secondary);
    font-size: 12px;
    cursor: pointer;
}

.section-edit-btn:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
}

/* 每日行程编辑按钮 */
.day-edit-btn {
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 4px;
    background: var(--bg-glass);
    color: var(--text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}

.day-edit-btn:hover {
    background: var(--primary-light);
    color: var(--primary-color);
}

/* 模态框 */
.editor-modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
    z-index: 2000;
    align-items: center;
    justify-content: center;
}

.editor-modal.active {
    display: flex;
}

.editor-content {
    background: var(--bg-panel-solid);
    border-radius: 12px;
    width: 90%;
    max-width: 500px;
    max-height: 80vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color);
}

.editor-title {
    font-size: 16px;
    font-weight: 600;
}

.editor-close {
    width: 32px;
    height: 32px;
    border: none;
    background: none;
    font-size: 24px;
    color: var(--text-muted);
    cursor: pointer;
}

.editor-body {
    padding: 20px;
    overflow-y: auto;
    flex: 1;
}

.editor-footer {
    padding: 16px 20px;
    border-top: 1px solid var(--border-color);
    display: flex;
    justify-content: flex-end;
    gap: 12px;
}

/* 编辑表单 */
.editor-modal .form-group {
    margin-bottom: 16px;
}

.editor-modal .form-group label {
    display: block;
    font-size: 12px;
    color: var(--text-muted);
    margin-bottom: 6px;
}

.editor-modal .form-group input,
.editor-modal .form-group select,
.editor-modal .form-group textarea {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-glass);
    color: var(--text-primary);
    font-size: 14px;
}

.editor-modal .form-row {
    display: flex;
    gap: 12px;
}

.editor-modal .form-row .form-group {
    flex: 1;
}
```

---

## 5. 文件改动清单

| 文件 | 改动内容 |
|------|---------|
| `templates/roadbook_template.html` | 1. 添加 section-header 包裹 section-title<br>2. 添加编辑按钮<br>3. 添加 editor-modal HTML<br>4. 添加 CSS 样式<br>5. 添加 JS 函数：openBasicInfoEditor, openDailyEditor, saveEditor, closeEditor<br>6. 修改 displayDailyItinerary 添加编辑按钮<br>7. 添加辅助函数 recalculateBudget, recalculateTotalDistance |

---

## 6. 验证方案

1. **测试基本信息编辑**
   - 点击"编辑"按钮 → 修改标题/天数 → 保存 → 验证显示更新

2. **测试每日行程编辑**
   - 点击 day-card 的 ✏️ 按钮 → 修改目的地/景点 → 保存 → 验证显示更新

3. **测试天气刷新**
   - 修改目的地后保存 → 验证天气数据重新获取

4. **测试保存文件**
   - 编辑后点击"💾 保存" → 下载 JSON → 验证修改已保存
