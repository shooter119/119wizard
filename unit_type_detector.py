#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单位类型智能识别模块
功能：从地址或警情描述中识别单位类型，匹配合适的火灾处置方案
优先级：单位火灾 > 普通民房火灾
"""

import re
import json
import os
import logging

# 获取模块所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 配置日志（仅控制台输出，不写文件）
logging.basicConfig(
    level=logging.WARNING,  # 默认只输出警告及以上
    format='%(asctime)s - %(message)s'
)


class UnitTypeDetector:
    """单位类型检测器"""

    def __init__(self, fire_cases_file=None):
        """初始化检测器"""
        # 默认使用完整版数据库
        if fire_cases_file is None:
            fire_cases_file = os.path.join(BASE_DIR, 'data', 'fire_cases_complete.json')
        # 单位类型关键词映射表
        self.unit_keywords = {
            '仓库': {
                'keywords': ['仓库', '物流园', '储运中心', '配送中心', '冷链仓库', '货运站', '仓储'],
                'fire_type': 'warehouse',
                'fire_type_name': '仓库火灾',
                'priority': 'critical',
                'aliases': ['物资仓库', '物流仓库', '货运仓库', '仓储中心']
            },
            '工厂': {
                'keywords': ['工厂', '厂', '企业', '公司', '制造', '生产', '加工', '车间', '厂房', '作坊', '工棚'],
                'fire_type': 'large_span_factory',
                'fire_type_name': '工业火灾',
                'priority': 'critical',
                'aliases': ['加工厂', '制造厂', '生产企业', '小作坊']
            },
            '加油站': {
                'keywords': ['加油站', '加气站', '油库', '储油站', '油站'],
                'fire_type': 'gas_station',
                'fire_type_name': '加油站火灾',
                'priority': 'critical',
                'aliases': ['CNG加气站', 'LNG加气站']
            },
            '化工': {
                'keywords': ['化工', '化工厂', '石化', '化学', '危化品', '危化', '精细化工'],
                'fire_type': 'chemical',
                'fire_type_name': '危化品火灾',
                'priority': 'critical',
                'aliases': ['石油化工', '化工厂']
            },
            '商场': {
                'keywords': ['商场', '购物中心', '超市', '百货', '卖场', '商业广场'],
                'fire_type': 'shopping_mall',
                'fire_type_name': '人员密集场所火灾',
                'priority': 'high',
                'aliases': ['大型商场', '购物中心']
            },
            '酒店': {
                'keywords': ['酒店', '宾馆', '旅馆', '饭店', '餐饮', '餐厅', 'KTV', '娱乐场所'],
                'fire_type': 'hotel',
                'fire_type_name': '人员密集场所火灾',
                'priority': 'high',
                'aliases': ['宾馆酒店', '度假酒店']
            },
            '医院': {
                'keywords': ['医院', '卫生院', '诊所', '医疗', '养老院', '福利院'],
                'fire_type': 'hospital',
                'fire_type_name': '敏感场所火灾',
                'priority': 'high',
                'aliases': ['卫生院', '诊所']
            },
            '学校': {
                'keywords': ['学校', '幼儿园', '小学', '中学', '大学', '培训', '教育'],
                'fire_type': 'school',
                'fire_type_name': '人员密集场所火灾',
                'priority': 'high',
                'aliases': ['幼儿园', '培训中心', '教育机构']
            },
            '小区': {
                'keywords': ['小区', '公寓', '住宅', '居民楼', '小区', '家园', '花园'],
                'fire_type': 'residential',
                'fire_type_name': '民用建筑火灾',
                'priority': 'normal',
                'aliases': ['住宅小区', '居民小区']
            },
            '办公': {
                'keywords': ['写字楼', '办公楼', '商务楼', '大厦', '办公楼', '商务大厦'],
                'fire_type': 'office',
                'fire_type_name': '高层建筑火灾',
                'priority': 'normal',
                'aliases': ['办公楼', '写字楼']
            },
            '车库': {
                'keywords': ['车库', '停车场', '地下车库', '地下室'],
                'fire_type': 'garage',
                'fire_type_name': '地下空间火灾',
                'priority': 'normal',
                'aliases': ['地下车库']
            }
        }

        # 加载火灾案例数据库
        try:
            with open(fire_cases_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.fire_cases = {case['id']: case for case in data['case_types']}
        except:
            self.fire_cases = {}

    def detect_unit_type(self, address, case_description='', amap_response=None):
        """
        检测单位类型（增强版 - 结合高德API）

        Args:
            address: 地址信息
            case_description: 警情描述
            amap_response: 高德API返回的结果（可选）

        Returns:
            dict: {
                'detected': bool,
                'unit_type': str,
                'unit_name': str,
                'fire_type': str,
                'fire_type_name': str,
                'priority': str,
                'confidence': float,
                'source': 'amap' or 'keyword'  # 标识数据来源
            }
        """
        print(f"🔍 检测单位类型...")
        combined_text = f"{address} {case_description}".lower()

        detected_units = []

        # 方法1：优先使用高德API返回的信息
        if amap_response and amap_response.get('formatted_address'):
            amap_address = amap_response['formatted_address']
            print(f"   高德返回地址：{amap_address}")

            # 检查高德返回的地址中是否包含单位关键词
            for unit_type, info in self.unit_keywords.items():
                for keyword in info['keywords']:
                    if keyword in amap_address:
                        # 找到了！使用高德的识别结果（权威性最高）
                        unit_name = self._extract_unit_name_from_amap(amap_address, keyword)

                        detected_units.append({
                            'type': unit_type,
                            'name': unit_name,
                            'fire_type': info['fire_type'],
                            'fire_type_name': info['fire_type_name'],
                            'priority': 'critical',  # 高德API识别的优先级最高
                            'confidence': 0.95,  # 置信度很高
                            'matched_keywords': [keyword],
                            'source': 'amap'
                        })
                        print(f"   ✅ 高德API识别：{info['fire_type_name']}")
                        break  # 找到一个就停止（避免误判）

        # 方法2：如果高德没识别到，使用关键词匹配
        if not detected_units:
            print(f"   使用关键词匹配...")
            # 排除性关键词：如果单位名称后面紧跟着这些词，说明起火点在单位外部
            peripheral_keywords = ['门口', '对面', '附近', '路边', '路口', '外围', '道口', '围墙外']
            
            for unit_type, info in self.unit_keywords.items():
                match_count = 0
                matched_keywords = []

                # 检查关键词
                for keyword in info['keywords']:
                    if keyword in combined_text:
                        # 检查关键词后是否紧跟排除性词汇
                        # 比如 "优蔓酒店门口"
                        pattern = rf"{keyword}[^，。]*?({'|'.join(peripheral_keywords)})"
                        if re.search(pattern, combined_text):
                            print(f"   ⚠️  检测到单位关键词 '{keyword}'，但地点在 '{re.search(pattern, combined_text).group(1)}'，降低优先级")
                            continue # 这里直接跳过，因为用户说明了在外面
                            
                        match_count += 1
                        matched_keywords.append(keyword)

                # 检查别名
                for alias in info.get('aliases', []):
                    if alias.lower() in combined_text:
                        pattern = rf"{alias}[^，。]*?({'|'.join(peripheral_keywords)})"
                        if re.search(pattern, combined_text):
                            continue
                        match_count += 2
                        matched_keywords.append(alias)

                if match_count > 0:
                    unit_name = self._extract_unit_name(combined_text, matched_keywords)

                    detected_units.append({
                        'type': unit_type,
                        'name': unit_name,
                        'fire_type': info['fire_type'],
                        'fire_type_name': info['fire_type_name'],
                        'priority': info['priority'],
                        'confidence': min(match_count * 0.3, 1.0),
                        'matched_keywords': matched_keywords,
                        'source': 'keyword'
                    })

        # 未检测到单位
        if not detected_units:
            print(f"   未检测到单位类型，按民用建筑处理")
            return {
                'detected': False,
                'unit_type': None,
                'unit_name': None,
                'fire_type': 'residential_building',
                'fire_type_name': '民用建筑火灾',
                'priority': 'normal',
                'confidence': 0.0,
                'source': 'default'
            }

        # 选择优先级最高的
        detected_units.sort(key=lambda x: (
            self._priority_score(x['priority']),
            x['confidence']
        ), reverse=True)

        best_match = detected_units[0]

        print(f"\n🏢 检测到单位类型：{best_match['fire_type_name']}")
        print(f"   优先级：{best_match['priority']} ({'高德API识别' if best_match['source'] == 'amap' else '关键词匹配'})")
        print(f"   单位名称：{best_match['name']}")
        print(f"   置信度：{best_match['confidence']:.1%}")

        # 记录日志
        logging.info(f"单位检测 | 地址:{address} | 单位:{best_match['name']} | 类型:{best_match['fire_type_name']} | 优先级:{best_match['priority']} | 来源:{best_match['source']}")

        return {
            'detected': True,
            'unit_type': best_match['type'],
            'unit_name': best_match['name'],
            'fire_type': best_match['fire_type'],
            'fire_type_name': best_match['fire_type_name'],
            'priority': best_match['priority'],
            'confidence': best_match['confidence'],
            'source': best_match['source']
        }

    def _extract_unit_name_from_amap(self, amap_address, keyword):
        """从高德返回的地址中提取单位名称"""
        # 在关键词前后提取一些文本作为单位名称
        parts = amap_address.split(keyword)
        if len(parts) > 1:
            # 提取关键词前面的部分
            before = parts[0].split()[-1] if parts[0] else ''
            return f"{before}{keyword}"
        return keyword

    def _extract_unit_name(self, text, keywords):
        """从文本中提取单位名称"""
        # 简单实现：使用第一个匹配的关键词周围的文本
        for keyword in keywords:
            if keyword in text:
                # 尝试提取更完整的名称
                # 例如："某某物流园仓库" → "某某物流园"
                pattern = rf'([^\s，。]+(?:{keyword}|园区|中心|广场))'
                match = re.search(pattern, text)
                if match:
                    return match.group(1).strip()

                # 如果上面的模式没匹配到，返回关键词本身
                return keyword

        return "未知单位"

    def _priority_score(self, priority):
        """将优先级转换为数值"""
        scores = {
            'critical': 100,
            'high': 80,
            'normal': 50,
            'low': 20
        }
        return scores.get(priority, 0)

    def get_fire_case_info(self, fire_type):
        """根据火灾类型获取处置信息"""
        if fire_type in self.fire_cases:
            return self.fire_cases[fire_type]
        else:
            # 如果没有对应的类型，返回民房火灾
            return self.fire_cases.get('residential_building', {})


# ==================== 使用示例 ====================

if __name__ == '__main__':
    detector = UnitTypeDetector()

    print("=" * 60)
    print("🏢 单位类型识别测试")
    print("=" * 60)

    # 测试用例
    test_cases = [
        {
            'address': '浙江省衢州市龙游县某街道某某仓库',
            'description': '仓库起火，浓烟滚滚'
        },
        {
            'address': '浙江省衢州市龙游县东华街道XX小区3栋',
            'description': '居民楼火灾'
        },
        {
            'address': '浙江省衢州市龙游县某某化工有限公司',
            'description': '化工厂起火'
        },
        {
            'address': '浙江省衢州市龙游县横山镇XX工厂',
            'description': '厂房火灾'
        },
        {
            'address': '浙江省衢州市龙游县东华街道XX加油站',
            'description': '加油站在起火'
        }
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}：{case['address']}")
        print(f"描述：{case['description']}")

        result = detector.detect_unit_type(case['address'], case['description'])

        if result['detected']:
            print(f"\n✅ 检测到单位类型：{result['fire_type_name']}")
            print(f"   优先级：{result['priority']}")
            print(f"   置信度：{result['confidence']:.1%}")

            # 获取对应的处置要点
            case_info = detector.get_fire_case_info(result['fire_type'])
            if case_info:
                print(f"\n📋 建议的处置要点（预览）：")
                content = case_info.get('content', {})
                if content.get('safety_tips'):
                    print(f"   安全提示：{content['safety_tips'][0][:50]}...")
        else:
            print(f"\n未检测到单位，按民用建筑处理")
