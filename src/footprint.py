# 足迹地图数据聚合模块
import os
import json
from collections import defaultdict
from datetime import datetime

from config import get_output_base_dir


class FootprintAggregator:
    """足迹数据聚合器"""

    def __init__(self, output_dir=None):
        self.output_dir = output_dir or get_output_base_dir()

    def scan_trajectories(self):
        """扫描 output 目录下所有轨迹数据"""
        trajectories = []

        if not os.path.exists(self.output_dir):
            return trajectories

        for item in os.listdir(self.output_dir):
            item_path = os.path.join(self.output_dir, item)
            if not os.path.isdir(item_path):
                continue

            data_file = os.path.join(item_path, 'data_converted.json')
            if os.path.exists(data_file):
                try:
                    with open(data_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    trajectories.append({
                        'dir_name': item,
                        'dir_path': item_path,
                        'data': data
                    })
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: 读取轨迹数据失败 {data_file}: {e}")

        return trajectories

    def aggregate(self):
        """聚合所有轨迹数据"""
        trajectories = self.scan_trajectories()

        if not trajectories:
            return self._empty_result()

        # 按城市分组
        city_groups = defaultdict(lambda: {
            'name': '',
            'province': '',
            'lat': 0,
            'lng': 0,
            'trip_count': 0,
            'visit_dates': set(),
            'total_photos': 0,
            'cover_photo': None,
            'locations': []
        })

        total_days = 0
        total_photos = 0
        provinces = set()
        cities = set()

        for traj in trajectories:
            traj_data = traj['data']
            if not isinstance(traj_data, list):
                continue

            # 统计总天数
            day_segments = set()
            for point in traj_data:
                if 'day_segment' in point:
                    day_segments.add(point['day_segment'])
            total_days += len(day_segments)

            for point in traj_data:
                admin = point.get('administrative', {})
                city = admin.get('city', '')
                province = admin.get('province', '')

                if not city:
                    continue

                city_key = f"{province}/{city}"
                group = city_groups[city_key]

                # 更新基本信息（只取第一次的值）
                if not group['name']:
                    group['name'] = city
                    group['province'] = province
                    group['lat'] = point.get('latitude_tran', 0)
                    group['lng'] = point.get('longitude_tran', 0)
                    group['locations'].append(point.get('place_name', ''))

                # 累加统计数据
                group['trip_count'] += 1
                group['total_photos'] += point.get('photo_count', 0)
                total_photos += point.get('photo_count', 0)

                # 收集访问日期
                for photo in point.get('photo', []):
                    ts = photo.get('timestamp', '')
                    if ts:
                        try:
                            date = ts.split('T')[0]
                            group['visit_dates'].add(date)
                        except (ValueError, IndexError):
                            pass

                # 更新省份/城市集合
                if province:
                    provinces.add(province)
                if city:
                    cities.add(city)

        # 构建locations列表
        locations = []
        for city_key, group in city_groups.items():
            if not group['name']:
                continue

            # 选择封面照片（取该城市第一个照片）
            cover_photo = None
            for traj in trajectories:
                for point in traj['data']:
                    admin = point.get('administrative', {})
                    if admin.get('city') == group['name'] and admin.get('province') == group['province']:
                        photos = point.get('photo', [])
                        if photos:
                            cover_photo = photos[0].get('thumbnail_path')
                            if cover_photo:
                                # 补全路径
                                cover_photo = f"{traj['dir_name']}/{cover_photo}"
                            break
                if cover_photo:
                    break

            locations.append({
                'name': group['name'],
                'province': group['province'],
                'lat': group['lat'],
                'lng': group['lng'],
                'trip_count': group['trip_count'],
                'visit_dates': sorted(list(group['visit_dates'])),
                'total_photos': group['total_photos'],
                'cover_photo': cover_photo
            })

        # 构建时间线
        timeline = []
        for loc in locations:
            for date in loc['visit_dates']:
                timeline.append({
                    'date': date,
                    'location': loc['name'],
                    'province': loc['province'],
                    'trip_count': loc['trip_count']
                })
        timeline.sort(key=lambda x: x['date'], reverse=True)

        return {
            'total_trips': len(trajectories),
            'total_days': total_days,
            'total_photos': total_photos,
            'provinces_visited': sorted(list(provinces)),
            'cities_visited': sorted(list(cities)),
            'locations': locations,
            'timeline': timeline[:50]  # 限制最近50条
        }

    def _empty_result(self):
        """返回空结果"""
        return {
            'total_trips': 0,
            'total_days': 0,
            'total_photos': 0,
            'provinces_visited': [],
            'cities_visited': [],
            'locations': [],
            'timeline': []
        }


def get_footprint_summary():
    """获取足迹汇总数据（供 Flask API 调用）"""
    aggregator = FootprintAggregator()
    return aggregator.aggregate()
