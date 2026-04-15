"""AI 路书生成器 - 使用 DeepSeek API 生成标准路书 JSON"""
import json
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


# JSON Schema 模板（来自 docs/route_template.json）
ROUTE_SCHEMA_TEMPLATE = """{
  "basic_info": {
    "title": "路书标题",
    "travel_date_start": "yyyy-MM-dd",
    "travel_date_end": "yyyy-MM-dd",
    "days": 天数,
    "car_type": "车型",
    "people_count": 人数,
    "room_count": 房间数,
    "total_distance_km": 全程里程,
    "fuel_consumption": "油耗如6.5L/100km",
    "fuel_price": 油价如8.5,
    "elevation_range": "海拔范围如20-1400m",
    "high_altitude_warning": false,
    "route_summary": "路线概要"
  },
  "daily_itinerary": [
    {
      "day_number": 1,
      "date": "yyyy-MM-dd",
      "origin": "出发地",
      "destination": "目的地",
      "distance_km": 当日里程,
      "duration_hours": 车程小时,
      "elevation_m": "海拔范围",
      "route": "途经路线",
      "highlights": ["景点1", "景点2"],
      "accommodation": "住宿地点",
      "food": ["美食1", "美食2"],
      "tips": ["提示1", "提示2"],
      "gas_station": "加油地点"
    }
  ],
  "budget": {
    "transportation": {
      "fuel_total_liters": 总油耗升,
      "fuel_cost": 油费,
      "toll_fees": 过路费,
      "transportation_total": 交通合计,
      "per_person": 人均交通费
    },
    "accommodation": [
      { "location": "住宿地点", "type": "酒店类型", "price_per_room": 每间房价, "nights": 晚数, "rooms": 房间数 }
    ],
    "food": {
      "daily_budget_per_person": 人均日餐饮预算,
      "days": 天数,
      "per_person": 人均餐饮,
      "group_total": 团队餐饮合计
    },
    "tickets": [
      { "item": "景点名", "total": 金额, "remark": "备注" }
    ],
    "misc": [
      { "item": "杂费项", "total": 金额 }
    ],
    "grand_total": {
      "per_person": 人均总费用,
      "group_total": 团队总费用
    }
  },
  "checklist": [
    {
      "category": "分类如证件",
      "items": ["事项1", "事项2"]
    }
  ]
}"""


SYSTEM_PROMPT = """你是一个专业的自驾旅行路书规划助手。请根据用户提供的旅行信息，生成符合标准JSON格式的自驾路书。

重要要求：
1. 只输出JSON，不要输出任何其他内容
2. JSON必须严格遵循提供的Schema格式
3. 路线要合理，包含真实的景点和地名
4. 预算要根据车型、天数、人数合理估算
5. 每日行程要实际可行，车程时间合理
6. 住宿推荐要包含具体地点和价格
7. **住宿信息分两处：daily_itinerary每条记录的 accommodation 为地点名称字符串；budget.accommodation 为数组，含 location/type/price_per_room/nights/rooms**
8. 美食推荐要体现当地特色
9. 出行清单要实用全面
10. **门票和杂费分开：budget.tickets 为数组含 item/total/remark；budget.misc 为数组含 item/total**
11. **route_summary 字段必须使用"→"箭头连接各地点**，格式为"大理→丽江→香格里拉→大理"，不能使用自然语言描述
12. **fuel_price 油价字段必填，根据当前地区油价合理估算（如 8-9 元/升）**
13. **所有日期字段使用 yyyy-MM-dd 格式，如 2026-07-15**"""


USER_PROMPT_TEMPLATE = """请基于以下信息生成标准JSON格式的路书数据：

- 目的地：{destination}
- 出发日期：{travel_date_start}
- 返回日期：{travel_date_end}
- 天数：{days}天
- 人数/房数：{people_count}人/{room_count}间
- 车型：{car_type}
- 预算偏好：{budget_preference}
- 特殊需求：{special_requirements}

请严格按照以下JSON Schema格式输出（只输出JSON，不要其他内容）：
{schema_template}"""


class RoadbookGenerator:
    """DeepSeek API 路书生成器"""

    def __init__(self, api_key: str, api_url: str = "https://api.deepseek.com/v1", model: str = "deepseek-chat"):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

    def generate(self, user_input: dict) -> dict:
        """生成路书 JSON

        Args:
            user_input: {
                "destination": str,      # 目的地
                "travel_date": str,      # 出发日期 YYYY-MM-DD
                "days": int,              # 天数
                "people_count": int,      # 人数
                "room_count": int,       # 房间数
                "car_type": str,          # 车型
                "budget_preference": str, # 预算偏好
                "special_requirements": str  # 特殊需求
            }

        Returns:
            {"status": "success", "data": {...}}
            {"status": "error", "error": str}
        """
        # 验证必填字段（days 可根据日期自动计算）
        required = ["destination", "travel_date_start", "travel_date_end", "people_count", "car_type"]
        for field in required:
            if not user_input.get(field):
                return {"status": "error", "error": f"缺少必填字段: {field}"}

        # 转换日期格式（YYYY-MM-DD 保持不变，AI schema 也用 yyyy-MM-dd）
        formatted_date_start = user_input["travel_date_start"]
        formatted_date_end = user_input["travel_date_end"]

        # 计算天数（如果未提供）
        days = user_input.get("days")
        if not days:
            try:
                d1 = datetime.strptime(formatted_date_start, "%Y-%m-%d")
                d2 = datetime.strptime(formatted_date_end, "%Y-%m-%d")
                days = (d2 - d1).days + 1
            except:
                days = 7  # 默认7天
        days = max(1, days)

        # 构建 Prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            destination=user_input["destination"],
            travel_date_start=formatted_date_start,
            travel_date_end=formatted_date_end,
            days=days,
            people_count=user_input["people_count"],
            room_count=user_input.get("room_count", 1),
            car_type=user_input["car_type"],
            budget_preference=user_input.get("budget_preference", "舒适"),
            special_requirements=user_input.get("special_requirements", "无"),
            schema_template=ROUTE_SCHEMA_TEMPLATE
        )

        try:
            # 调用 DeepSeek API
            import openai

            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.api_url
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4096
            )

            content = response.choices[0].message.content

            # 提取 JSON
            json_str = self._extract_json(content)

            # 解析 JSON
            roadbook_data = json.loads(json_str)

            # 验证必需字段
            if not self._validate_roadbook(roadbook_data):
                return {"status": "error", "error": "生成的JSON格式不符合要求"}

            # 重新计算 grand_total（AI 计算经常出错）
            self._recalculate_grand_total(roadbook_data)

            return {"status": "success", "data": roadbook_data}

        except ImportError:
            return {"status": "error", "error": "请安装 openai 库: pip install openai"}
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}\n原始内容: {content[:500] if 'content' in dir() else 'N/A'}")
            return {"status": "error", "error": f"JSON解析失败: {str(e)}"}
        except Exception as e:
            logger.error(f"AI生成失败: {e}")
            return {"status": "error", "error": str(e)}

    def _extract_json(self, content: str) -> str:
        """从 AI 返回内容中提取 JSON 字符串"""
        # 去除 markdown 代码块
        content = content.strip()

        # 检查是否被 ```json 或 ``` 包裹
        if content.startswith("```"):
            # 去除 ```json 或 ```
            lines = content.split("\n")
            # 找到第一个 ``` 后的内容
            json_start = -1
            json_end = -1
            for i, line in enumerate(lines):
                if line.strip().startswith("```") and json_start == -1:
                    json_start = i + 1
                elif line.strip() == "```" and json_start != -1:
                    json_end = i
                    break
            if json_start > 0 and json_end > json_start:
                content = "\n".join(lines[json_start:json_end])
            elif json_start > 0:
                content = "\n".join(lines[json_start:])

        # 尝试直接解析
        try:
            json.loads(content)
            return content
        except:
            pass

        # 查找 JSON 对象
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json_match.group(0)

        raise ValueError("无法从返回内容中提取JSON")

    def _validate_roadbook(self, data: dict) -> bool:
        """验证生成的 JSON 是否符合基本要求"""
        required_keys = ["basic_info", "daily_itinerary", "budget"]
        for key in required_keys:
            if key not in data:
                logger.warning(f"缺少必需字段: {key}")
                return False

        # basic_info 必填字段
        basic_info = data.get("basic_info", {})
        basic_required = ["travel_date_start", "travel_date_end", "days", "car_type", "people_count"]
        for key in basic_required:
            if key not in basic_info:
                logger.warning(f"basic_info 缺少字段: {key}")
                return False

        # daily_itinerary 必填字段
        daily = data.get("daily_itinerary", [])
        if not isinstance(daily, list) or len(daily) == 0:
            logger.warning("daily_itinerary 为空或格式错误")
            return False

        daily_required = ["day_number", "date", "origin", "destination"]
        for day in daily:
            for key in daily_required:
                if key not in day:
                    logger.warning(f"daily_itinerary 某天缺少字段: {key}")
                    return False

        return True

    def _recalculate_grand_total(self, data: dict) -> None:
        """重新计算 grand_total（AI 计算经常出错）"""
        budget = data.get("budget", {})
        people = data.get("basic_info", {}).get("people_count", 1)

        # 交通费用
        transport = budget.get("transportation", {})
        transportation_total = transport.get("transportation_total", 0)
        transportation_per_person = transport.get("per_person", 0)

        # 住宿费用（数组求和）
        accommodation = budget.get("accommodation", [])
        accommodation_total = 0
        if isinstance(accommodation, list):
            for acc in accommodation:
                price = acc.get("price_per_room", 0)
                nights = acc.get("nights", 1)
                rooms = acc.get("rooms", 1)
                accommodation_total += price * nights * rooms
        accommodation_per_person = round(accommodation_total / people) if people > 0 else 0

        # 餐饮费用
        food = budget.get("food", {})
        food_group_total = food.get("group_total", 0)
        food_per_person = food.get("per_person", 0)

        # 门票费用
        tickets = budget.get("tickets", [])
        tickets_total = 0
        if isinstance(tickets, list):
            for t in tickets:
                tickets_total += t.get("total", 0)
        tickets_per_person = round(tickets_total / people) if people > 0 else 0

        # 杂费
        misc = budget.get("misc", [])
        misc_total = 0
        if isinstance(misc, list):
            for m in misc:
                misc_total += m.get("total", 0)
        misc_per_person = round(misc_total / people) if people > 0 else 0

        # 计算总计
        group_total = (
            transportation_total
            + accommodation_total
            + food_group_total
            + tickets_total
            + misc_total
        )
        per_person = (
            transportation_per_person
            + accommodation_per_person
            + food_per_person
            + tickets_per_person
            + misc_per_person
        )

        # 更新 budget
        data["budget"]["grand_total"] = {
            "per_person": per_person,
            "group_total": group_total
        }

    def generate_stream(self, user_input: dict):
        """流式生成路书 - yield AI 输出的每个 chunk

        Args:
            user_input: 同 generate() 的 user_input

        Yields:
            str: SSE 格式的数据块 "data: {json}\n\n"
        """
        # 验证必填字段
        required = ["destination", "travel_date_start", "travel_date_end", "people_count", "car_type"]
        for field in required:
            if not user_input.get(field):
                yield f"data: {json.dumps({'type': 'error', 'error': f'缺少必填字段: {field}'})}\n\n"
                return

        # 转换日期格式
        formatted_date_start = user_input["travel_date_start"]
        formatted_date_end = user_input["travel_date_end"]

        # 计算天数
        days = user_input.get("days")
        if not days:
            try:
                d1 = datetime.strptime(formatted_date_start, "%Y-%m-%d")
                d2 = datetime.strptime(formatted_date_end, "%Y-%m-%d")
                days = (d2 - d1).days + 1
            except:
                days = 7
        days = max(1, days)

        # 构建 Prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            destination=user_input["destination"],
            travel_date_start=formatted_date_start,
            travel_date_end=formatted_date_end,
            days=days,
            people_count=user_input["people_count"],
            room_count=user_input.get("room_count", 1),
            car_type=user_input["car_type"],
            budget_preference=user_input.get("budget_preference", "舒适"),
            special_requirements=user_input.get("special_requirements", "无"),
            schema_template=ROUTE_SCHEMA_TEMPLATE
        )

        try:
            import openai

            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.api_url
            )

            # 发送开始信号
            yield json.dumps({'type': 'start'}) + "\n\n"

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4096,
                stream=True
            )

            full_content = ""
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    full_content += content
                    yield f"data: {json.dumps({'type': 'chunk', 'content': content, 'full': full_content})}\n\n"

            # 流结束，发送完成信号带上完整内容供验证
            yield f"data: {json.dumps({'type': 'done', 'full': full_content})}\n\n"

        except ImportError:
            yield f"data: {json.dumps({'type': 'error', 'error': '请安装 openai 库: pip install openai'})}\n\n"
        except Exception as e:
            logger.error(f"AI流式生成失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


def generate_roadbook(user_input: dict, api_key: str, api_url: str = None, model: str = None) -> dict:
    """便捷函数：生成路书

    Args:
        user_input: 用户输入信息
        api_key: DeepSeek API Key
        api_url: API URL (可选)
        model: 模型名称 (可选)

    Returns:
        {"status": "success", "data": {...}}
        {"status": "error", "error": str}
    """
    generator = RoadbookGenerator(
        api_key=api_key,
        api_url=api_url or "https://api.deepseek.com/v1",
        model=model or "deepseek-chat"
    )
    return generator.generate(user_input)
