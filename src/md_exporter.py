"""路书 Markdown 导出模块"""
import os
from datetime import datetime


def export_roadbook_to_markdown(roadbook_data, output_path):
    """
    将路书数据导出为 Markdown 文件

    Args:
        roadbook_data: 路书 JSON 数据
        output_path: 输出文件路径
    """
    content = _generate_markdown(roadbook_data)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return output_path


def _generate_markdown(roadbook_data):
    """生成 Markdown 内容"""
    basic_info = roadbook_data.get('basic_info', {})
    daily_itinerary = roadbook_data.get('daily_itinerary', [])
    scenic_guides = roadbook_data.get('scenic_guides', {})
    budget = roadbook_data.get('budget', {})
    checklist = roadbook_data.get('checklist', [])

    lines = []

    # ========== 标题区 ==========
    title = basic_info.get('title', '旅行路书')
    lines.append(f"# {title}")
    lines.append("")

    route_summary = basic_info.get('route_summary', '')
    if route_summary:
        lines.append(f"> {route_summary}")
        lines.append("")

    # 基本信息行
    travel_start = basic_info.get('travel_date_start', '')
    travel_end = basic_info.get('travel_date_end', '')
    days = basic_info.get('days', 0)
    people = basic_info.get('people_count', 0)
    car_type = basic_info.get('car_type', '')
    distance = basic_info.get('total_distance_km', 0)

    info_items = []
    if travel_start and travel_end:
        info_items.append(f"旅行时间：{travel_start} 至 {travel_end}")
    if days:
        info_items.append(f"共 {days} 天")
    if people:
        info_items.append(f"出行人数：{people} 人")
    if car_type:
        info_items.append(f"车型：{car_type}")
    if distance:
        info_items.append(f"总里程：{distance}km")

    if info_items:
        lines.append("> " + " | ".join(info_items))
        lines.append("")

    lines.append("---")
    lines.append("")

    # ========== 行程概览 ==========
    lines.append("## 📋 行程概览")
    lines.append("")
    lines.append("| 日期 | 星期 | 出发地 | 目的地 | 里程 | 车程 |")
    lines.append("|------|------|--------|--------|------|------|")

    for day in daily_itinerary:
        date_str = day.get('date', '')
        weekday = _get_weekday(date_str)
        origin = day.get('origin', '-')
        destination = day.get('destination', '-')
        distance_km = day.get('distance_km', '-')
        duration = day.get('duration_hours', '-')

        lines.append(f"| {date_str} | {weekday} | {origin} | {destination} | {distance_km}km | {duration}h |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ========== 每日行程详情 ==========
    lines.append("## 🚗 每日行程详情")
    lines.append("")

    for day in daily_itinerary:
        day_num = day.get('day_number', '')
        date_str = day.get('date', '')
        weekday = _get_weekday(date_str)
        origin = day.get('origin', '-')
        destination = day.get('destination', '-')
        distance_km = day.get('distance_km', '-')
        duration = day.get('duration_hours', '-')
        elevation = day.get('elevation_m', '-')
        route = day.get('route', '')
        highlights = day.get('highlights', [])
        accommodation = day.get('accommodation', '')
        food = day.get('food', [])
        tips = day.get('tips', [])
        route_stops = day.get('route_stops', [])

        lines.append(f"### Day {day_num}：{date_str}（{weekday}）")
        lines.append("")
        lines.append(f"**今日路线**：{origin} → {destination}")
        lines.append("")
        lines.append(f"- 里程：{distance_km}km | 车程：约 {duration} 小时")
        if elevation and elevation != '-':
            lines.append(f"- 海拔：{elevation}")
        lines.append("")

        # 途经站点
        if route_stops:
            lines.append("**途经站点**：")
            for stop in route_stops:
                stop_type = _get_stop_type_name(stop.get('type', ''))
                stop_name = stop.get('name', '')
                stop_desc = stop.get('description', '')
                if stop_desc:
                    lines.append(f"- 【{stop_type}】{stop_name} — {stop_desc}")
                else:
                    lines.append(f"- 【{stop_type}】{stop_name}")
            lines.append("")

        # 今日亮点
        if highlights:
            highlights_str = "、".join(highlights[:3]) if len(highlights) > 3 else "、".join(highlights)
            lines.append(f"**今日亮点**：{highlights_str}")
            lines.append("")

        # 住宿推荐
        if accommodation:
            lines.append(f"**住宿推荐**：{accommodation}")
            lines.append("")

        # 美食推荐
        if food:
            food_str = "、".join(food[:3]) if len(food) > 3 else "、".join(food)
            lines.append(f"**美食推荐**：{food_str}")
            lines.append("")

        # 温馨贴士
        if tips:
            lines.append(f"**温馨贴士**：")
            for tip in tips[:2]:
                lines.append(f"- {tip}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ========== 景点攻略 ==========
    if scenic_guides:
        lines.append("## 🎫 景点攻略")
        lines.append("")

        for spot_name, guide in scenic_guides.items():
            name = guide.get('name', spot_name)
            location = guide.get('location', '-')
            opening_hours = guide.get('opening_hours', '-')
            visit_time = guide.get('recommended_visit_time', '-')
            ticket_info = guide.get('ticket_info', '-')
            description = guide.get('description', '')
            tips_list = guide.get('tips', [])

            lines.append(f"### {name}")
            lines.append("")
            lines.append(f"- 📍 **位置**：{location}")
            lines.append(f"- ⏰ **开放时间**：{opening_hours}")
            lines.append(f"- ⌛ **建议游览**：{visit_time}")
            lines.append(f"- 🎟️ **门票**：{ticket_info}")
            lines.append("")

            if description:
                lines.append(f"**景点介绍**：")
                lines.append(f"{description}")
                lines.append("")

            if tips_list:
                lines.append(f"**游览贴士**：")
                for tip in tips_list[:3]:
                    lines.append(f"- {tip}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # ========== 费用预算 ==========
    lines.append("## 💰 费用预算")
    lines.append("")

    # 交通费用
    trans = budget.get('transportation', {})
    if trans:
        lines.append("### 交通费用")
        lines.append("")
        lines.append("| 项目 | 金额 |")
        lines.append("|------|------|")
        fuel_total = trans.get('fuel_total_liters', 0)
        fuel_cost = trans.get('fuel_cost', 0)
        toll_fees = trans.get('toll_fees', 0)
        trans_total = trans.get('transportation_total', 0)
        trans_per_person = trans.get('per_person', 0)

        lines.append(f"| 油费（{fuel_total}L） | ¥{fuel_cost} |")
        lines.append(f"| 过路费 | ¥{toll_fees} |")
        lines.append(f"| **交通小计** | **¥{trans_total}** |")
        lines.append("")

    # 住宿费用
    accommodations = budget.get('accommodation', [])
    if accommodations:
        lines.append("### 住宿费用")
        lines.append("")
        lines.append("| 地点 | 类型 | 单价 | 晚数 | 房间 | 小计 |")
        lines.append("|------|------|------|------|------|------|")

        acc_total = 0
        for acc in accommodations:
            location = acc.get('location', '-')
            acc_type = acc.get('type', '-')
            price = acc.get('price_per_room', 0)
            nights = acc.get('nights', 0)
            rooms = acc.get('rooms', 0)
            total = price * nights * rooms
            acc_total += total

            lines.append(f"| {location} | {acc_type} | ¥{price}/晚 | {nights}晚 | {rooms}间 | ¥{total} |")

        lines.append(f"| **住宿合计** | | | | | **¥{acc_total}** |")
        lines.append("")

    # 餐饮费用
    food = budget.get('food', {})
    if food:
        lines.append("### 餐饮费用")
        lines.append("")
        daily_budget = food.get('daily_budget_per_person', 0)
        food_days = food.get('days', 0)
        food_per_person = food.get('per_person', 0)
        food_total = food.get('group_total', 0)

        lines.append(f"- 人均日预算：¥{daily_budget}/人/天")
        lines.append(f"- 餐饮合计：¥{food_total}（{food_days}天 × {people}人）")
        lines.append("")

    # 景点门票
    tickets = budget.get('tickets', [])
    if tickets:
        lines.append("### 景点门票")
        lines.append("")
        lines.append("| 景点 | 金额 | 备注 |")
        lines.append("|------|------|------|")

        ticket_total = 0
        for ticket in tickets:
            item = ticket.get('item', '-')
            total = ticket.get('total', 0)
            remark = ticket.get('remark', '-')
            ticket_total += total
            lines.append(f"| {item} | ¥{total} | {remark} |")

        lines.append(f"| **门票合计** | **¥{ticket_total}** | |")
        lines.append("")

    # 总计
    grand_total = budget.get('grand_total', {})
    if grand_total:
        lines.append("### 费用总计")
        lines.append("")
        lines.append("| 费用项 | 人均 | 团体合计 |")
        lines.append("|--------|------|----------|")

        gp_per = grand_total.get('per_person', 0)
        gp_group = grand_total.get('group_total', 0)

        lines.append(f"| 交通 | ¥{trans.get('per_person', 0)} | ¥{trans.get('transportation_total', 0)} |")
        lines.append(f"| 住宿 | - | ¥{acc_total} |")
        lines.append(f"| 餐饮 | ¥{food_per_person} | ¥{food_total} |")
        lines.append(f"| 门票 | - | ¥{ticket_total} |")
        lines.append(f"| **总计** | **¥{gp_per}** | **¥{gp_group}** |")
        lines.append("")

    # ========== 出行清单 ==========
    if checklist:
        lines.append("## ✅ 出行清单")
        lines.append("")

        for category in checklist:
            category_name = category.get('category', '其他')
            items = category.get('items', [])

            lines.append(f"### {category_name}")
            lines.append("")
            if items:
                for item in items:
                    lines.append(f"- [ ] {item}")
            else:
                lines.append("- （无）")
            lines.append("")

    # ========== 页脚 ==========
    lines.append("---")
    lines.append("")
    lines.append("> 📄 本行程由 **RoadBook** 自动生成")
    lines.append("> 🌐 访问 [roadbook.top](https://roadbook.top) 查看更多")

    return "\n".join(lines)


def _get_weekday(date_str):
    """获取星期几"""
    if not date_str:
        return "-"
    try:
        weekday_num = datetime.strptime(date_str, '%Y-%m-%d').weekday()
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        return weekdays[weekday_num]
    except:
        return "-"


def _get_stop_type_name(stop_type):
    """获取站点类型中文名称"""
    type_names = {
        'start': '出发',
        'gas': '加油',
        'transit': '途经',
        'scenic': '景点',
        'end': '终点',
        'food': '美食',
        'accommodation': '住宿'
    }
    return type_names.get(stop_type, stop_type)


def get_markdown_filename(roadbook_data):
    """根据路书数据生成 Markdown 文件名"""
    basic_info = roadbook_data.get('basic_info', {})
    title = basic_info.get('title', '路书')
    start_date = basic_info.get('travel_date_start', '')

    # 清理文件名中的非法字符
    title = title.replace('/', '-').replace('\\', '-').replace('*', '-').replace('?', '-')

    if start_date:
        return f"路书_{title}_{start_date}.md"
    else:
        return f"路书_{title}.md"
