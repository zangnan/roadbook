# 路书模板功能扩展详细规划

## 功能概览

| 功能 | 优先级 | 复杂度 | 状态 |
|------|--------|--------|------|
| 本地保存 | P0 | 中 | 待实现 |
| 路书编辑 | P0 | 高 | 规划中 |
| 天气集成 | P1 | 低 | 规划中 |

---

## 1. 本地保存功能

### 功能描述
- 将当前路书保存到本地 JSON 文件
- 支持加载本地保存的路书文件
- 在上传区域添加"加载本地文件"按钮

### UI 设计

#### 1.1 上传区域改造
```
┌─────────────────────────────────┐
│  📁                             │
│  点击或拖拽上传路书JSON文件        │
│  支持 .json 格式文件              │
│                                  │
│  [上传文件]  [从本地加载]          │
└─────────────────────────────────┘
```

#### 1.2 保存按钮
在"开始路径规划"按钮旁添加"保存路书"按钮

### 技术实现

#### 前端改动

1. **保存路书函数**
```javascript
function saveRoadbookToFile() {
    if (!currentRoadbook) {
        alert('请先生成或加载路书');
        return;
    }

    const blob = new Blob([JSON.stringify(currentRoadbook, null, 2)], {
        type: 'application/json'
    });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `路书_${currentRoadbook.basic_info?.title || '未命名'}_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
```

2. **加载本地保存的按钮**
```html
<button class="btn btn-secondary" onclick="loadLocalRoadbook()">
    从本地加载
</button>
<input type="file" id="localFileInput" accept=".json" style="display:none">

<script>
document.getElementById('localFileInput').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (evt) => {
            try {
                const data = JSON.parse(evt.target.result);
                currentRoadbook = data;
                parseAndDisplayRoadbook(data);
            } catch (err) {
                alert('文件格式错误');
            }
        };
        reader.readAsText(file);
    }
});
</script>
```

3. **自动保存到 localStorage（可选）**
```javascript
// 生成或加载路书后自动保存
function autoSave() {
    if (currentRoadbook) {
        localStorage.setItem('roadbook_draft', JSON.stringify(currentRoadbook));
    }
}

// 页面加载时恢复
function restoreFromAutoSave() {
    const saved = localStorage.getItem('roadbook_draft');
    if (saved) {
        try {
            const data = JSON.parse(saved);
            // 显示恢复提示
            if (confirm('发现未保存的路书，是否恢复？')) {
                currentRoadbook = data;
                parseAndDisplayRoadbook(data);
            }
        } catch (e) {}
    }
}
```

### 文件改动
- `templates/roadbook_template.html`: 添加保存/加载按钮和 JS 逻辑

---

## 2. 路书编辑功能（规划中）

### 功能描述
用户可以对 AI 生成的路书进行手动编辑，包括：
- 编辑基本信息（标题、天数、人数等）
- 编辑每日行程（出发地、目的地、景点、住宿等）
- 编辑预算信息
- 编辑出行清单

### UI 设计

#### 2.1 编辑入口
- 在"基本信息"卡片右上角添加"编辑"按钮
- 点击进入编辑模式，卡片变为可编辑状态

#### 2.2 编辑模式 UI
```
┌─────────────────────────────┐
│ 基本信息                      │
│ [完成编辑] [取消]             │
├─────────────────────────────┤
│ 标题：________________       │
│ 出行日期：___________        │
│ 天数：___ 人数：___         │
│ ...                         │
└─────────────────────────────┘
```

---

## 3. 天气集成功能（规划中）

### 功能描述
- 显示行程期间各目的地的天气预报
- 集成墨迹天气/和风天气等免费 API
- 展示在每日行程详情中

### 技术方案
- API：和风天气（免费，每日 1000 次调用）
- 后端接口获取数据
- 前端展示天气信息

---

## 实施日志

### 2026-04-10
- [x] 完成功能规划文档

### 2026-04-13
- [x] 实现本地保存功能 ✅
- [x] 实现天气集成功能 ✅
- [x] 路书编辑功能 ✅
