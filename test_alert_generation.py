#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
警情出动提示生成测试脚本
功能：根据输入的警情数据，自动生成出动提示
新增功能：智能识别单位类型，优先匹配对应处置方案
"""

import json
import requests
import os
from datetime import datetime
from unit_type_detector import UnitTypeDetector

# ==================== 配置 ====================
# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 加载配置文件
def load_config():
    config_path = os.path.join(BASE_DIR, 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

CONFIG = load_config()

# API 配置（从 config.json 读取）
AMAP_KEY = CONFIG.get('api_keys', {}).get('amap', '')
AMAP_ENDPOINT = CONFIG.get('amap', {}).get('endpoint', 'https://restapi.amap.com')
QWEATHER_KEY = CONFIG.get('api_keys', {}).get('qweather', '')
QWEATHER_ENDPOINT = CONFIG.get('qweather', {}).get('endpoint', 'https://m97p435htr.re.qweatherapi.com/v7')

# 车辆配置数据库（示例）
# 车辆数据库（从JSON文件读取）
def load_vehicle_db():
    try:
        json_path = os.path.join(BASE_DIR, 'data', 'vehicles.json')
        if not os.path.exists(json_path):
             return []
        
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

VEHICLE_DB = load_vehicle_db()

# 联系人数据库（从JSON文件读取）
def load_contacts():
    """加载联系人数据并转换为字典格式"""
    try:
        json_path = os.path.join(BASE_DIR, 'data', 'contacts.json')
        if not os.path.exists(json_path):
             print("⚠️  联系人数据库文件不存在，使用空数据")
             return {}
             
        with open(json_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            
        contacts_map = {}
        
        # 辅助函数：添加联系人到映射表
        def add_to_map(key, person):
            if not key: return
            if key not in contacts_map:
                contacts_map[key] = {}
            
            # 简单的优先级逻辑：书记/主任优先作为 primary
            current_primary = contacts_map[key].get('primary')
            position = person.get('position', '')
            is_leader = any(role in position for role in ['书记', '主任', '镇长', '所长'])
            
            new_contact = {
                "name": person.get('name', ''),
                "position": position,
                "phone": person.get('phone', '')
            }

            if not current_primary:
                contacts_map[key]['primary'] = new_contact
            elif is_leader and '书记' not in current_primary.get('position', ''):
                 # 如果新联系人是领导且当前主联系人不是书记，则替换
                 contacts_map[key]['backup'] = current_primary
                 contacts_map[key]['primary'] = new_contact
            else:
                 contacts_map[key]['backup'] = new_contact

        count = 0
        for entry in raw_data:
            # 优先使用村名作为键
            if entry.get('village'):
                add_to_map(entry['village'], entry)
                count += 1
            # 如果没有村名，使用乡镇名
            elif entry.get('township'):
                add_to_map(entry['township'], entry)
                count += 1
                
        print(f"✅ 加载联系人数据库：覆盖 {len(contacts_map)} 个地点")
        return contacts_map
    except Exception as e:
        print(f"❌ 加载联系人数据库失败: {e}")
        return {}

CONTACTS = load_contacts()

# 案件类型数据库（从JSON文件读取）
def load_case_types():
    try:
        # 优先使用完整版数据库
        case_path = os.path.join(BASE_DIR, 'data', 'fire_cases_complete.json')
        with open(case_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"✅ 加载完整版数据库：{data['total_cases']}个案例类型")
            return {case['id']: case for case in data['case_types']}
    except:
        try:
            # 回退到示例数据库
            example_path = os.path.join(BASE_DIR, 'data', 'fire_cases_example.json')
            with open(example_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"⚠️  回退到示例数据库：{len(data['case_types'])}个案例类型")
                return {case['id']: case for case in data['case_types']}
        except:
            print(f"❌ 无法加载案例数据库")
            return {}

CASE_TYPES = load_case_types()

# 初始化单位类型检测器
unit_detector = UnitTypeDetector()

# 消防站坐标数据库（从JSON文件读取）
def load_station_coordinates():
    """加载消防站坐标数据"""
    try:
        station_path = os.path.join(BASE_DIR, 'data', 'station_coordinates_quzhou.json')
        with open(station_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

STATION_COORDS = load_station_coordinates()

# ==================== API调用 ====================

def get_weather(location="330825"):
    """获取天气及其预警信息 (使用和风天气 QWeather)"""
    # 常用参数
    params = {
        "key": QWEATHER_KEY,
        "location": location,
        "lang": "zh"
    }
    
    weather_data = {
        "temperature": "",
        "weather": "",
        "winddirection": "",
        "windpower": "",
        "humidity": "",
        "warning": ""
    }

    try:
        # 1. 获取实况天气
        now_url = f"{QWEATHER_ENDPOINT}/weather/now"
        now_resp = requests.get(now_url, params=params, timeout=10)
        now_json = now_resp.json()
        
        if now_json.get("code") == "200":
            now = now_json.get("now", {})
            weather_data.update({
                "temperature": f"{now.get('temp', '')}°C",
                "weather": now.get('text', ''),
                "winddirection": now.get('windDir', ''),
                "windpower": f"{now.get('windScale', '')}级",
                "humidity": f"{now.get('humidity', '')}%"
            })
        else:
            print(f"⚠️  和风天气实况API返回错误 code: {now_json.get('code')}, {now_json.get('msg', '')}")
        
        # 2. 获取天气预警
        warning_url = f"{QWEATHER_ENDPOINT}/warning/now"
        warning_resp = requests.get(warning_url, params=params, timeout=10)
        warning_json = warning_resp.json()
        
        if warning_json.get("code") == "200":
            warnings = warning_json.get("warning", [])
            if warnings:
                warning_texts = [w.get("title", "") for w in warnings if w.get("title")]
                if warning_texts:
                    weather_data["warning"] = "；".join(warning_texts)

        return weather_data if weather_data["weather"] else None

    except Exception as e:
        print(f"❌ 和风天气API调用异常: {e}")
    return None

def geocode(address, city="330800", nearby_point=None):
    """地址解析（带备用搜索）
    
    Args:
        address: 地址字符串
        city: 城市adcode，默认为衢州市(330800)，用于限定搜索范围
        nearby_point: 参考坐标点 "lon,lat"，用于筛选最近的结果
    """
    
    # helper to perform the actual request
    def _do_geocode_request(_addr, _city=None):
        url = f"{AMAP_ENDPOINT}/v3/geocode/geo"
        params = {
            "key": AMAP_KEY,
            "address": _addr
        }
        if _city:
            params["city"] = _city
            
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if data.get("status") == "1" and data.get("geocodes"):
                return data["geocodes"][0]
        except Exception as e:
            print(f"地址解析API调用出错: {e}")
        return None

    # 简单距离估算（用于排序）
    def _calc_distance_squared(pt1_str, pt2_str):
        try:
            lon1, lat1 = map(float, pt1_str.split(','))
            lon2, lat2 = map(float, pt2_str.split(','))
            return (lon1 - lon2) ** 2 + (lat1 - lat2) ** 2
        except:
            return float('inf')

    # 1. 地址清洗与结构化 (Structuring & Cleaning)
    processed_address = address
    request_city = city
    
    # 1.1 自动补全“省份”前缀
    # 如果以“衢州市”等本省地级市开头但没有省份，自动拼接“浙江省”
    # 高德索引机制对“省+市”开头的字符串响应更优
    import re
    if not address.startswith("浙江省"):
        # 匹配常见的浙江省地级市
        zj_cities = ["衢州市", "杭州市", "金华市", "宁波市", "温州市", "嘉兴市", "绍兴市", "湖州市", "台州市", "舟山市", "丽水市"]
        for c in zj_cities:
            if address.startswith(c):
                processed_address = "浙江省" + address
                print(f"🔧 自动补全省份前缀: {processed_address}")
                break

    # 1.1.b 清洗干扰词 (针对解析失败优化)
    # 逻辑：去除如 "某厂房"、"起火" 等描述性词汇，仅保留纯地址部分
    original_for_clean = processed_address
    for noise in ["起火", "冒烟", "发生火灾", "火灾", "火情", "某厂房", "某公司", "某店", "某处"]:
        processed_address = processed_address.replace(noise, "")
    if processed_address != original_for_clean:
         print(f"🧹 地址干扰词清洗: '{original_for_clean}' -> '{processed_address}'")

    # 1.2 提取城市信息
    # 尝试提取地址中的城市作为 city 参数，缩减搜索范围
    city_match = re.search(r'(.+?市)', processed_address)
    if city_match:
        extracted_city = city_match.group(1)
        # 只有当提取的城市不在排除列表中（避免误提取“超市”等）
        if "超市" not in extracted_city:
            request_city = extracted_city
            # 如果提取的城市不是衢州市，说明是跨区域，打印提示
            if "衢州" not in extracted_city:
                print(f"🌍 提取到跨区域城市: {extracted_city}")
            else:
                # 即使是衢州，显式指定也能帮助API更精准
                pass
    
    # 1.3 针对高速场景的静默优化
    # 将数字 404 识别为里程点，在发送给 API 时辅助匹配
    # 逻辑：如果包含“高速”且以数字结尾
    # 1.3 针对高速场景的静默优化
    # 将数字 404 识别为里程点，在发送给 API 时辅助匹配
    # 逻辑：如果包含“高速”且以数字结尾
    mileage_struct = None
    fallback_query = None
    
    if "高速" in address:
        # 提取末尾的数字 或 Kxxx
        # 优先匹配 Kxxx 或 xxx公里
        k_match = re.search(r'[Kk](\d+)', address)
        mile_match = re.search(r'(\d+)公里', address)
        
        mile_num = None
        if k_match:
            mile_num = k_match.group(1)
        elif mile_match:
            mile_num = mile_match.group(1)
        else:
            # 最后尝试匹配末尾的数字
            num_match = re.search(r'(\d+)$', address)
            if num_match:
                mile_num = num_match.group(1)
                
        if mile_num:
            # 这里的技巧是：在不改变原地址信息的前提下，构建一个更适合搜索的“结构化查询词”
            # 假如原地址是 "衢州西上高速杭州方向404"
            # 我们可以提取出 "衢州西" (入口/POI) 和 "404" (桩号)
            
            # 简单策略：如果原始搜索失败，我们将尝试搜索 "高速名 + K + 数字"
            # 先尝试提取高速名，如 G60
            highway_match = re.search(r'G\d+|S\d+|[\u4e00-\u9fa5]+高速', address)
            
            if highway_match:
                highway_name = highway_match.group(0)
                # 如果匹配到的是"上高速"，这通常不是高速名，而是动作
                if "上高速" in highway_name:
                    # 尝试提取"上高速"前面的部分作为关键点
                    pre_match = re.search(r'([\u4e00-\u9fa5]+?)(?:上高速)', address)
                    if pre_match:
                        # 比如 "衢州西上高速" -> "衢州西"
                        point_name = pre_match.group(1)
                        # 去除行政区划前缀（取最后一个行政单位后的内容）
                        import re
                        split_res = re.split(r'[市区县]', point_name)
                        # 取最后一个非空的部分
                        valid_parts = [p for p in split_res if p]
                        if valid_parts:
                            point_name = valid_parts[-1]
                        
                        # 再次检查长度，如果过长可能仍然包含冗余
                        if len(point_name) > 6:
                             point_name = point_name[-4:]
                        mileage_struct = f"{point_name}高速 K{mile_num}" 
                        fallback_query = f"{point_name}收费站" # 生成回退查询词
                        print(f"🧠 检测到'上高速'动作，构造组合查询: '{mileage_struct}' (回退词: '{fallback_query}')")
                else:
                    mileage_struct = f"{highway_name} K{mile_num}"
                    print(f"🧠 预构建高速桩号结构化查询: '{mileage_struct}' (将在POI搜索中使用)")
            else:
                 # 没找到明显的高速名，直接用全地址+K
                 mileage_struct = f"{processed_address} K{mile_num}"

    # 2. 尝试标准解析 (使用清洗后的地址)
    geocode_result = _do_geocode_request(processed_address, request_city)
    
    # 如果指定了城市但解析失败，尝试解除限制重试
    if not geocode_result and request_city:
        print(f"⚠️  即定城市({request_city})解析失败，尝试全国搜索...")
        geocode_result = _do_geocode_request(address, None)

    # 距离校验：如果标准解析结果距离过远（>300公里），认为解析错误（如匹配到外省同名地点），强制进入POI搜索
    if geocode_result and nearby_point:
        dist_sq = _calc_distance_squared(nearby_point, geocode_result.get('location', '0,0'))
        # 粗略估算：经纬度差1度约111km。300km约2.7度。平方约7.3
        # 距离校验：如果标准解析结果距离过远（>75公里），认为解析错误（如匹配到外省同名地点），强制进入 POI 搜索
        if dist_sq > 0.5:
            print(f"⚠️  标准解析结果距离过远 ({geocode_result.get('formatted_address')})，可能是误匹配，强制尝试POI搜索...")
            geocode_result = None

    if geocode_result:
        # 检查是否需要更精确的POI搜索
        # 如果地址包含具体地点关键词（如服务区、出口），但由于标准解析只返回了道路或行政区划
        is_generic_result = geocode_result.get("level") in ["道路", "区县", "市", "省"]
        
        # 关键词列表：服务区、出口、入口、收费站、互通... 以及桩号(Kxxx, xxx公里)
        import re
        mileage_match = re.search(r'[Kk]\d+|\d+公里', address)
        # 精确地点关键词，如果标准解析只返回道路或区划，则强制触发针对这些词的 POI 搜索
        specific_keywords = [
            "服务区", "出口", "入口", "收费站", "互通", "加油站", "加气站",
            "大厦", "小区", "学校", "医院", "酒店", "宾馆", "旅馆", "饭店", 
        ]
        # 如果已经识别出了里程桩结构化信息，也认为是特定地址
        has_specific_keywords = any(k in address for k in specific_keywords) or bool(mileage_match) or bool(mileage_struct)
        # 如果标准解析结果等级太高（如区县、市），且地址中更具体（如包含路、号、村），则强制触发 POI 搜索
        is_coarse_result = geocode_result.get("level") in ["区县", "市", "省"]
        has_address_details = any(k in address for k in ["路", "街", "号", "村", "弄", "巷", "道"])
        
        # 综合判定是否需要更精确的搜索
        should_trigger_poi = (is_generic_result and has_specific_keywords) or (is_coarse_result and has_address_details)
        
        if should_trigger_poi:
            print(f"⚠️  解析结果等级为({geocode_result.get('level')})，尝试通过 POI 搜索获取更精确坐标...")
        else:
            return {
                "formatted_address": geocode_result.get("formatted_address", ""),
                "location": geocode_result.get("location", ""),
                "level": geocode_result.get("level", ""),
                "adcode": geocode_result.get("adcode", "")
            }
    
    # 3. 方案2: POI 关键词搜索（适用于高速公路、服务区等特殊地点）
    print(f"⚠️  标准地址解析失败或不够精确，尝试 POI 搜索: {processed_address}")
    
    # 针对高速公路地址的预处理
    search_keywords = processed_address
    
    # [新增] 高速方向语义转换 (G60沪昆/杭金衢)
    # 逻辑：服务区/POI通常以终点城市命名方向（如昆明/上海），但报警人常说下一大站（如江西/杭州）
    if any(kw in address for kw in ["G60", "沪昆", "杭金衢"]):
        original_keywords = search_keywords
        if "江西方向" in search_keywords:
            search_keywords = search_keywords.replace("江西方向", "昆明方向")
        elif "往江西" in search_keywords:
            search_keywords = search_keywords.replace("往江西", "往昆明")
            
        if "杭州方向" in search_keywords:
            search_keywords = search_keywords.replace("杭州方向", "上海方向")
        elif "往杭州" in search_keywords:
             search_keywords = search_keywords.replace("往杭州", "往上海")
             
        if search_keywords != original_keywords:
            print(f"🔁 高速方向语义修正: '{original_keywords}' -> '{search_keywords}'")
    
    # 3.1 优先使用预构建的结构化查询词 (里程桩号优化)
    if mileage_struct:
         print(f"🚀 启用高速桩号加强搜索: '{mileage_struct}'")
         search_keywords = mileage_struct
         
    elif "高速" in address and ("往" in address or "方向" in address):
        # 尝试提取关键信息
        import re
        poi_match = re.search(r'([\u4e00-\u9fa5]+(?:服务区|出口|入口|收费站|互通))', address)
        highway_match = re.search(r'([A-Z0-9]+(?:[\u4e00-\u9fa5]+高速)?)', address)
        
        if poi_match:
            new_keywords = ""
            if highway_match:
                new_keywords += highway_match.group(1) + " "
            new_keywords += poi_match.group(1)
            print(f"💡 提取关键信息进行搜索: {new_keywords}")
            search_keywords = new_keywords

    try:
        poi_url = f"{AMAP_ENDPOINT}/v3/place/text"
        poi_params = {
            "key": AMAP_KEY,
            "keywords": search_keywords,
            "city": city if city else "330800", # POI搜索可以使用默认城市作为优先
            "citylimit": "false",  # 不限制城市，扩大搜索范围
            "extensions": "base",
            "offset": 20  # 获取更多结果以便筛选
        }
        
        # 如果有参考点，传入 location 参数帮助API优化排序（虽然我们也会手动排）
        if nearby_point:
            poi_params['location'] = nearby_point
            
        resp = requests.get(poi_url, params=poi_params, timeout=10)
        data = resp.json()
        
        # 自动回退机制：如果精确搜索失败且有回退词
        is_fallback = False
        if (data.get("status") != "1" or not data.get("pois")) and fallback_query:
            print(f"⚠️  精确桩号搜索失败，尝试回退搜索收费站: {fallback_query}")
            poi_params['keywords'] = fallback_query
            # 回退时可以移除 location 参数以避免过度限制，或者保留
            resp = requests.get(poi_url, params=poi_params, timeout=10)
            data = resp.json()
            is_fallback = True
            
        if data.get("status") == "1" and data.get("pois"):
            pois = data["pois"]
            
            # 如果有参考坐标，根据距离排序
            if nearby_point:
                print(f"📏 根据距离参考点 {nearby_point} 对 {len(pois)} 个结果进行排序...")
                pois.sort(key=lambda p: _calc_distance_squared(nearby_point, p.get('location', '0,0')))
                
                # 打印最优选和最差选的对比，用于调试
                best = pois[0]
                print(f"   ✅ 最优匹配: {best.get('name')} ({best.get('address')})")
            
            poi = pois[0]
            print(f"✅ POI 搜索成功: {poi.get('name', '')}")
            result = {
                "formatted_address": poi.get("address", "") or poi.get("name", ""),
                "location": poi.get("location", ""),
                "level": "POI",
                "adcode": poi.get("adcode", "")
            }
            if is_fallback:
                result['_is_fallback'] = True
                result['_fallback_target'] = fallback_query
            return result
    except Exception as e:
        print(f"POI 搜索失败: {e}")
    
    # 如果POI搜索失败，但之前有标准解析结果，则回退使用标准解析结果
    if geocode_result:
        return {
            "formatted_address": geocode_result.get("formatted_address", ""),
            "location": geocode_result.get("location", ""),
            "level": geocode_result.get("level", ""),
            "adcode": geocode_result.get("adcode", "")
        }
    
    return None


def get_direction(origin, destination):
    """路径规划"""
    url = f"{AMAP_ENDPOINT}/v3/direction/driving"
    params = {
        "key": AMAP_KEY,
        "origin": origin,
        "destination": destination,
        "strategy": "10",
        "extensions": "all" 
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("route"):
            route = data["route"]
            path = route.get("paths", [{}])[0]
            distance_m = int(path.get('distance', 0))
            duration_s = int(path.get('duration', 0))
            
            # 解析路况信息
            traffic_status = "道路畅通"
            congested_dist = 0
            slow_dist = 0
            
            for step in path.get('steps', []):
                for tmc in step.get('tmcs', []):
                    status = tmc.get('status', '')
                    dist = int(tmc.get('distance', 0))
                    if status in ['拥堵', '严重拥堵']:
                        congested_dist += dist
                    elif status == '缓行':
                        slow_dist += dist
            
            if congested_dist > 500: # 超过500米才报拥堵
                traffic_status = f"拥堵约{congested_dist/1000:.1f}公里"
            elif slow_dist > 1000: # 超过1公里才报缓行
                traffic_status = f"缓行约{slow_dist/1000:.1f}公里"
            elif congested_dist > 0 or slow_dist > 0:
                 traffic_status = "部分路段行驶缓慢"
                 
            return {
                "distance": f"{distance_m/1000:.1f}", # 改为纯数字字符串，方便后续格式化
                "duration": f"{duration_s//60}",
                "distance_m": distance_m,
                "duration_s": duration_s,
                "traffic": traffic_status
            }
    except Exception as e:
        print(f"路径规划失败: {e}")
    return None

# ==================== 数据处理 ====================

def normalize_str(s):
    """字符串标准化：处理全角半角、空格、大小写"""
    if not s: return ""
    # 全角转半角
    full_chars = "＋－＊／＝（）［］｛｝＜＞"
    half_chars = "+-*/=()[]{}<>"
    trans_table = str.maketrans(full_chars, half_chars)
    s = s.translate(trans_table)
    return s.replace(" ", "").lower()

def calculate_force_stats(vehicles, station_name=None):
    """计算出动力量统计 (基于数据库动态查询)"""
    total_water = 0
    total_foam = 0
    total_crew = 0 
    vehicle_count = len(vehicles)
    
    # 1. 严格筛选本站车辆
    search_pool = VEHICLE_DB
    if station_name:
        station_keyword = station_name.replace("消防救援站", "").replace("站", "").replace("大队", "")
        station_matches = [v for v in VEHICLE_DB if station_keyword in v.get("消防站名称", "")]
        
        if station_matches:
            search_pool = station_matches
            print(f"📡 已锁定消防站：{station_name}，在该站库内匹配车辆...")
        else:
            print(f"⚠️ 数据库中未找到消防站：{station_name}，将在全库匹配...")

    for v_str in vehicles:
        v_normalized = normalize_str(v_str)
        best_match = None
        current_max_score = 0
        
        # 针对 "15+3" 这种容量描述进行正则匹配
        import re
        capacity_pattern = re.search(r'(\d+(?:\.\d+)?)\+(\d+(?:\.\d+)?)', v_normalized)
        
        for db_v in search_pool:
            score = 0
            db_v_name = normalize_str(db_v.get("车辆名称", ""))
            db_brand = normalize_str(db_v.get("底盘品牌", ""))
            
            # --- 核心策略 1: 容量匹配 (最强加分) ---
            if capacity_pattern:
                target_w = float(capacity_pattern.group(1))
                target_f = float(capacity_pattern.group(2))
                
                db_w = float(db_v.get("载水量吨", 0) or 0)
                # 汇总泡沫量
                db_f = float(db_v.get("载B类泡沫吨", 0) or 0) + \
                       float(db_v.get("载A类泡沫吨", 0) or 0) + \
                       float(db_v.get("载泡沫量吨", 0) or 0)
                
                if abs(db_w - target_w) < 0.1 and abs(db_f - target_f) < 0.1:
                    score += 15 # 极高评分，通常是精准匹配
            
            # --- 核心策略 2: 名称/类别匹配 ---
            if v_normalized == db_v_name:
                score += 10
            
            # 类别关键词匹配
            categories = {
                "主战": ["主战", "城市主战", "cafs"],
                "水罐": ["水罐", "供水", "sg"],
                "泡沫": ["泡沫", "pm"],
                "抢险": ["抢险", "救援", "jy"],
                "举高": ["举高", "高喷", "云梯", "登高", "jg"],
                "排烟": ["排烟"],
                "战保": ["战保", "战勤"],
                "指挥": ["指挥", "通信", "tx"],
                "a类泡沫": ["a类", "压缩空气"]
            }
            
            for cat_name, kw_list in categories.items():
                input_has_cat = any(kw in v_normalized for kw in kw_list)
                db_has_cat = any(kw in db_v_name for kw in kw_list)
                if input_has_cat and db_has_cat:
                    score += 5
            
            # 品牌匹配 (辅助)
            if db_brand and db_brand in v_normalized:
                score += 3
            
            # 包含匹配
            if v_normalized in db_v_name or db_v_name in v_normalized:
                score += 1
                
            if score > current_max_score and score >= 4:
                current_max_score = score
                best_match = db_v
        
        # 结果累加
        water = 0
        foam = 0
        crew = 5
        
        if best_match:
            try:
                water = float(best_match.get("载水量吨", 0) or 0)
                foam_b = float(best_match.get("载B类泡沫吨", 0) or 0)
                foam_a = float(best_match.get("载A类泡沫吨", 0) or 0)
                foam_other = float(best_match.get("载泡沫量吨", 0) or 0) 
                foam = foam_b + foam_a + foam_other
            except:
                pass
        else:
            # 兜底估算
            if "水罐" in v_normalized: water = 10; foam = 0
            elif "泡沫" in v_normalized: water = 5; foam = 2
            elif "主战" in v_normalized: water = 3; foam = 1
            elif "+" in v_normalized and capacity_pattern:
                water = float(capacity_pattern.group(1))
                foam = float(capacity_pattern.group(2))
        
        total_water += water
        total_foam += foam
        total_crew += crew

    return {
        "vehicle_count": vehicle_count,
        "total_water": round(total_water, 1),
        "total_foam": round(total_foam, 1),
        "total_crew": total_crew
    }

def extract_location_from_address(address):
    """从地址中提取行政区划（县、街道/镇、村）"""
    import re
    
    if not address:
        return "", "", ""
    
    county = ""
    street = ""
    village = ""
    
    # 提取县
    county_match = re.search(r'([\u4e00-\u9fa5]+县)', address)
    if county_match:
        county = county_match.group(1)
    
    # 提取街道或镇
    street_match = re.search(r'([\u4e00-\u9fa5]+(?:街道|镇|乡))', address)
    if street_match:
        street = street_match.group(1)
    
    # 提取村名（包括"村"字）
    village_match = re.search(r'([\u4e00-\u9fa5]+村)', address)
    if village_match:
        village = village_match.group(1)
    
    return county, street, village

def normalize_station_name(station_name):
    """标准化消防站名称：将'某某站'转换为'某某消防救援站'"""
    if not station_name:
        return station_name

    # 如果已经包含"消防救援站"，直接返回
    if '消防救援站' in station_name:
        return station_name

    # 将"某某站"转换为"某某消防救援站"
    if station_name.endswith('站'):
        # 去掉"站"，添加"消防救援站"
        return station_name[:-1] + '消防救援站'

    # 其他情况直接返回
    return station_name

def validate_and_correct_address(address):
    """校验并纠正地址中的村名错别字"""
    if not address:
        return address, False

    # 常见错别字映射表（可根据需要扩展）
    common_typos = {
        '下洋村': '下杨村',
        '上洋村': '上杨村',
        # 可以继续添加其他常见的错别字
    }

    original_address = address
    corrected = False

    for wrong, correct in common_typos.items():
        if wrong in address:
            print(f"⚠️  检测到可能的错别字：'{wrong}' → '{correct}'")
            address = address.replace(wrong, correct)
            corrected = True

    if corrected:
        print(f"✅ 地址已自动纠正：")
        print(f"   原始：{original_address}")
        print(f"   纠正：{address}")

    return address, corrected

# ==================== 生成输出 ====================

def generate_alert(case_data):
    """生成警情出动提示"""

    # 1. 先解析地址获取 adcode（用于后续天气查询）
    address = case_data.get('address', '')
    # 校验并纠正地址中的错别字
    address, was_corrected = validate_and_correct_address(address)
    station = case_data.get('station', '永安路站')
    
    # 1.1 先获取消防站坐标（用于辅助地址解析）
    # 从数据库获取消防站坐标
    origin = None

    # 先尝试从坐标数据库中查找
    for station_key, station_info in STATION_COORDS.items():
        if station_key in station or station in station_key:
            if isinstance(station_info, dict):
                origin = station_info.get('location', '')
            else:
                origin = station_info
            break

    # 如果没有找到坐标，尝试动态查询
    if not origin:
        print(f"⚠️  未找到 {station} 的坐标，尝试动态查询...")
        full_station_name = normalize_station_name(station)
        # 注意：这里调用 geocode 查找消防站时，不需要 origin 参数
        station_geocode = geocode(f"浙江省衢州市{full_station_name}")
        if station_geocode:
            origin = station_geocode.get('location', '')
            print(f"✅ 查询消防站成功：{origin}")

    # 如果还是没有，使用默认坐标
    if not origin:
        print(f"⚠️  使用默认坐标（请手动添加 {station} 的坐标）")
        origin = "119.225046,29.035807"  # 默认坐标

    # 1.2 解析地址获取 adcode（及坐标）
    # 传入 origin 作为参考点，用于筛选最近的结果
    geocode_result = geocode(address, nearby_point=origin)
    
    # 获取消防站的 adcode 作为天气兜底
    # 尝试解析消防站地址获取其 adcode
    station_adcode = "330825" # 最后的硬保底（龙游县）
    
    # 尝试从 STATION_COORDS 中可能的元数据获取，或通过解析消防站名称获取
    # 如果前面动态查询过消防站
    if 'station_geocode' in locals() and station_geocode:
        station_adcode = station_geocode.get('adcode', "330825")
    else:
        # 尝试再次快速解析消防站以获取准确的 adcode
        full_station_name = normalize_station_name(station)
        st_res = geocode(f"浙江省衢州市{full_station_name}")
        if st_res:
            station_adcode = st_res.get('adcode', "330825")

    adcode = station_adcode  # 默认使用消防站区域天气
    formatted_address = address
    
    if geocode_result:
        formatted_address = geocode_result['formatted_address']
        # 只有当解析结果有明确 adcode 时才覆盖默认值
        if geocode_result.get('adcode'):
             adcode = geocode_result.get('adcode')
        print(f"📍 地址解析成功，adcode: {adcode}")
    else:
        print(f"⚠️ 地址解析失败，使用消防站所在区域({adcode})天气作为兜底")
    
    # 2. 根据报警地址获取天气信息 (优先使用坐标，和风天气支持经纬度查询)
    weather_location = origin
    if geocode_result:
        weather_location = geocode_result['location']
        
    weather = get_weather(weather_location)
    weather_info = ""
    if weather:
        temp = weather.get('temperature', '')
        if temp:
            weather_info = f"气温{temp}，"

        w = weather.get('weather', '')
        wp = weather.get('windpower', '')
        
        # 预警信息处理
        warning = weather.get('warning', '')
        warning_prefix = f"【预警：{warning}】" if warning else ""
        
        # 只在有特殊天气时才显示警告符号
        severe_weather = ['雨', '雪', '雾', '霾', '雷', '暴', '台风', '冰雹', '沙尘', '大风']
        has_severe = any(sw in w for sw in severe_weather) if w else False
        weather_warning_icon = " ⚠️" if has_severe or warning else ""
        
        weather_info += f"天气{w}{weather_warning_icon}" if w else ""
        weather_info += f"，{weather.get('winddirection', '')}风 {wp}" if wp else ""
        weather_info += f"，湿度{weather.get('humidity', '')}。"
        
        # 如果有预警，将其添加到末尾
        if warning:
            weather_info += f"\n注：{warning}"
            
        weather_info = weather_info.strip()
        if not weather_info.endswith("。") and "\n" not in weather_info:
            weather_info += "。"

    # === 智能单位类型检测（新增） ===
    print(f"\n{'='*60}")
    unit_detection = unit_detector.detect_unit_type(address)
    # 将检测结果保存到case_data中，供后续使用
    case_data['_unit_detection'] = unit_detection

    # 使用前面已解析的 geocode_result（避免重复调用）
    route_info = ""

    if geocode_result:
        location = geocode_result['location']
        route = get_direction(origin, location)

        if route:
            distance = route['distance']
            duration = route['duration']
            # 在地址路况中使用完整的消防站名称
            full_station_name = normalize_station_name(station)

            # 如果检测到单位，在地址路况中特别标注
            # 如果检测到单位，在地址路况中特别标注
            # 如果检测到单位，在地址路况中特别标注
            traffic_status = route.get('traffic', '路况未知')
            
            if unit_detection['detected']:
                # 提取单位名称和火灾类型
                unit_name = unit_detection.get('unit_name', '未知单位')
                fire_type_name = unit_detection.get('fire_type_name', '火灾')
                route_info = f"距{full_station_name}{distance}公里，约{duration}分钟（检测到：{unit_name}，{fire_type_name}），{traffic_status}。"
            else:
                route_info = f"距{full_station_name}{distance}公里，约{duration}分钟，{traffic_status}。"

            # 如果是回退定位（例如找不到具体桩号，定位到了收费站），添加说明
            if geocode_result.get('_is_fallback'):
                fallback_target = geocode_result.get('_fallback_target', '入口')
                route_info += f" (⚠️无法定位具体路牌，已计算至{fallback_target}距离)"
        # 补充天气和道路环境提示
        road_tips = ""
        if weather and ("雾" in weather_info or "雾" in weather.get('weather', '')):
            road_tips += "大雾天气，按需开雾灯双闪；"

        # 检查是否有"村"（使用正则避免匹配到“贺村”等大镇）
        import re
        if re.search(r'(?<!贺)村', address):
            road_tips += "村道狭窄，注意会车；"
            
        if road_tips:
             route_info += f"（{road_tips.rstrip('；')}）"
    else:
        # 在地址路况中使用完整的消防站名称
        full_station_name = normalize_station_name(station)
        route_info = f"{full_station_name}前往{formatted_address}（目的地尚不明确，请尽快核实）。"

    # 3. 出动力量统计
    vehicles = case_data.get('vehicles', [])
    force_stats = calculate_force_stats(vehicles, station)

    # 优先使用用户提供的人数，如果没有则使用计算值
    total_crew = case_data.get('personnel', force_stats['total_crew'])

    # 4. 案件类型信息 - 智能匹配（优先级：单位检测 > 用户输入）
    user_case_type = case_data.get('case_type', '民房起火')

    # 5. 案例类型信息 - 智能匹配（优先级：单位检测 > 用户输入）
    # 初始化为空字典
    case_data_info = {}

    # 优先使用单位类型检测结果
    if unit_detection['detected'] and unit_detection['priority'] in ['critical', 'high']:
        print(f"\n⚠️  检测到单位类型，优先使用：{unit_detection['fire_type_name']}")
        print(f"   用户输入类型：{user_case_type}")

        # 使用单位类型对应的火灾案例
        fire_case_id = unit_detection['fire_type']
        case_data_info = CASE_TYPES.get(fire_case_id, {})

        # 如果没有找到对应的案例，尝试使用相似的
        if not case_data_info or not case_data_info.get('content'):
            print(f"   ⚠️  数据库中暂无{unit_detection['fire_type_name']}的专门处置要点")
            print(f"   将使用危化品火灾（相似类型）的处置要点")
            case_data_info = CASE_TYPES.get('hazmat_transport', {})
    else:
        # 未检测到单位，使用用户输入的类型
        print(f"\n✅ 使用用户输入的火灾类型：{user_case_type}")

        # 遍历所有案例类型，查找匹配的
        # 特殊逻辑：如果地址包含"高速"且用户输入包含"火"或"车"，优先尝试匹配高速车辆火灾
        # 补充：如果文本中包含“漏油”、“抛锚”等关联高风险词汇，也强制匹配
        full_text = case_data.get('full_text', '')
        force_highway_check = False
        
        if "高速" in address or "G" in address or "S" in address:
            if "火" in user_case_type or "车" in user_case_type:
                 force_highway_check = True
            elif "漏油" in full_text or "抛锚" in full_text or "起火" in full_text:
                 force_highway_check = True
        
        if force_highway_check:
             hq_case = CASE_TYPES.get('highway_vehicle_fire')
             if hq_case:
                 print(f"🛣️  检测到高速场景，尝试匹配高速车辆火灾...")
                 case_data_info = hq_case

        if not case_data_info:
            for case_id, case_info in CASE_TYPES.items():
                # 检查名称、别名或关键词是否匹配
                if (user_case_type == case_info.get('name') or
                    user_case_type in case_info.get('aliases', []) or
                    any(keyword in user_case_type for keyword in case_info.get('keywords', []))):
                    case_data_info = case_info
                    break

        # 如果没有匹配到，使用默认的民用建筑火灾
        if not case_data_info:
            # 特殊逻辑：如果是车辆火灾，但没匹配到 case_info
            if user_case_type == '车辆火灾':
                 case_data_info = CASE_TYPES.get('highway_vehicle_fire', {})
                 if case_data_info:
                     # 深度拷贝或临时修改名称以便显示
                     case_data_info = case_data_info.copy()
                     if "高速" not in address:
                         case_data_info['name'] = "车辆火灾"
            else:
                 case_data_info = CASE_TYPES.get('residential_building', {})

    # === [重构] 优先级博弈：如果用户明确说是车辆火灾或特定的专项救援，且单位仅为背景，则以具体警情为主 ===
    # 逻辑：如果单位检测到的优先级只是 High (如酒店、商场) 而不是 Critical (如化工厂、仓库)，
    # 且用户输入是具体的车辆火灾或专项救援，则优先使用具体警情。
    specific_scenarios = ['车辆火灾', '身体部位被卡', '电梯困人', '高空救援', '车祸救援', '摘马蜂窝', '水域救援']
    if unit_detection['detected'] and unit_detection['priority'] == 'high':
        if user_case_type in specific_scenarios:
            print(f"   💡 虽然检测到单位 {unit_detection['unit_name']}，但警情明确为 {user_case_type}，优先使用该项处置要点")
            # 重新定位案例
            for cid, cinfo in CASE_TYPES.items():
                 if user_case_type == cinfo.get('name') or user_case_type in cinfo.get('aliases', []):
                     case_data_info = cinfo.copy()
                     if user_case_type == '车辆火灾' and "高速" not in address:
                         case_data_info['name'] = "车辆火灾"
                     break

    # === [新增/重构] 根据最终确定的案件类型，决定是否显示载水/泡沫信息 ===
    # 基础出动信息
    force_info = f"{station}出动{force_stats['vehicle_count']}车{total_crew}人"
    water_foam_info = ""
    
    # 判断显示逻辑：
    # 1. 默认为 True
    # 2. 如果是 '救援' 或 '社会救助' 类，且并未被识别为 '火灾' (例如高速车辆火灾)，则不显示
    # 3. 如果识别到的 case_data_info 的 category 是 '火灾'，强制显示
    
    show_water_foam = True
    
    # 【显示逻辑修正】只有在肯定用不到水和泡沫的场景才隐藏
    # 场景名：抓蛇、马蜂窝、开锁、开门、跳楼/轻生、电梯困人、水域救援等
    dry_scenarios = ['抓蛇', '马蜂窝', '蜂窝', '开锁', '开门', '破门', '跳楼', '轻生', '电梯', '水域', '落水', '溺水']
    
    for keyword in dry_scenarios:
        if keyword in user_case_type:
            show_water_foam = False
            break
            
    # 如果最终分类是火灾，则无论输入的关键词是什么，都必须显示
    if case_data_info.get('category') == '火灾':
        show_water_foam = True
        
    if show_water_foam:
        water_foam_info = f"，载水{force_stats['total_water']}吨，泡沫{force_stats['total_foam']}吨"
        force_info += water_foam_info

    # 5. 联动信息 - 使用纠偏后的地址 formatted_address 来查询
    contact_info = ""
    
    # 从纠偏后的地址中提取街道和村名
    corrected_county, corrected_street, corrected_village = extract_location_from_address(formatted_address)
    
    # 查询街道联系人
    if corrected_street and CONTACTS.get(corrected_street):
        street_contact = CONTACTS[corrected_street]['primary']
        contact_info += f"{corrected_street}{street_contact['position']}：{street_contact['phone']}；"
    
    # 查询村联系人
    if corrected_village and CONTACTS.get(corrected_village):
        village_contact = CONTACTS[corrected_village]['primary']
        contact_info += f"{corrected_village}{village_contact['position']}：{village_contact['phone']}"

    # 6. 生成最终输出
    # 构建各个章节内容
    safety_tips = get_section_content(case_data_info, 'safety_tips')
    handling_points = get_section_content(case_data_info, 'handling_points')
    tactics = get_section_content(case_data_info, 'tactics')
    characteristics = get_section_content(case_data_info, 'characteristics')
    warnings = get_section_content(case_data_info, 'warnings')

    output_lines = []
    output_lines.append("🚨 警情出动提示")
    output_lines.append("")
    
    # 基本信息
    output_lines.append(" 📋 基本信息")
    
    # 构建简洁的警情描述
    station = case_data.get('station', '')
    case_level = case_data.get('case_level', '')
    report_time = case_data.get('report_time', '')
    address = case_data.get('address', '')
    case_description = case_data.get('case_description', '')
    personnel = case_data.get('personnel', 0)
    vehicles = case_data.get('vehicles', [])
    
    # 原始警情描述或构建一个
    original_alert = case_data.get('original_alert', '')
    if original_alert:
        # 检查原始文字是否已包含出动信息（包含"出动"和"人"）
        final_alert = original_alert
        
        # [逻辑1] 如果包含出动信息，尝试插入载水泡沫信息
        if '出动' in original_alert and '人' in original_alert:
            # 如果需要显示水/泡沫，尝试插入到“x车x人”后面
            if show_water_foam and water_foam_info:
                import re
                # 匹配模式： "出动X车...Y人" (中间可能夹杂括号里的车辆详情)
                # 支持全角（）和半角 () 括号
                pattern = r'(出动\d+车(?:[（\(][^）\)]+[）\)])?\d+人)'
                if re.search(pattern, final_alert):
                    final_alert = re.sub(pattern, lambda m: m.group(1) + water_foam_info, final_alert)
        else:
             # [逻辑2] 原文不包含出动信息，手动拼接
            if not final_alert.endswith('。'):
                final_alert += '。'
            final_alert += f"{station}出动{len(vehicles)}车{personnel}人{water_foam_info}前往处置。"

        # [新增] 如果地址被系统自动纠偏过（疑似错别字或同音字），追加特别提示
        if was_corrected:
             final_alert += "（地名疑似有误，抓紧确认）"

        output_lines.append(final_alert)
    else:
        # 如果没有原始警情，全自动生成
        generated_text = force_info + "前往处置。"
        if was_corrected:
             generated_text += "（地名疑似有误，抓紧确认）"
        output_lines.append(generated_text)
    
    # 天气信息
    output_lines.append("")
    output_lines.append("🌤 天气信息")
    output_lines.append(weather_info)
    
    # 地址路况
    output_lines.append("")
    output_lines.append("🚗 地址路况")
    output_lines.append(route_info)

    # 安全提示
    if safety_tips:
        output_lines.append("")
        output_lines.append(" ⚠️ 安全提示")
        output_lines.append(safety_tips)

    # 处置要点 - 使用数字编号格式
    if handling_points:
        output_lines.append("")
        output_lines.append("📝 处置要点")
        output_lines.append(format_handling_points(case_data_info))

    # 作战要则
    if tactics:
        output_lines.append("")
        output_lines.append(" 🎯 作战要则")
        output_lines.append(tactics)

    # 灾害特点
    if characteristics:
        output_lines.append("")
        output_lines.append("🔥 灾害特点")
        output_lines.append(characteristics)

    # 特别警示
    if warnings:
        output_lines.append("")
        output_lines.append("🚫 特别警示")
        output_lines.append(warnings)

    # 联动信息
    if contact_info:
        output_lines.append("")
        output_lines.append(" 📞 联动信息")
        output_lines.append(contact_info)

    output_lines.append("")

    output = '\n'.join(output_lines)

    return output


def format_handling_points(case_data):
    """格式化处置要点为数字编号格式"""
    if not case_data:
        return ""
    
    handling_points = case_data.get('content', {}).get('handling_points', [])
    if not handling_points:
        return ""
    
    lines = []
    for i, point in enumerate(handling_points, 1):
        if isinstance(point, dict):
            # 支持多种可能的键名：phase, type, name
            phase = point.get('phase') or point.get('type') or point.get('name') or ''
            actions = point.get('actions', [])
            lines.append(f"{i}、{phase}")
            for action in actions:
                lines.append(f"  • {action}")
        else:
            lines.append(f"{i}、{point}")
    
    return '\n'.join(lines)

def get_section_content(case_data, section):
    """获取章节内容，如果为空返回空字符串"""
    if not case_data:
        return ""

    content = case_data.get('content', {}).get(section, [])

    if not content:
        return ""

    if isinstance(content, list):
        formatted = []
        for item in content:
            if isinstance(item, dict):
                # 处理结构化数据（如处置要点分阶段）
                phase = item.get('phase', '')
                actions = item.get('actions', [])
                if phase:
                    formatted.append(f"**{phase}**")
                for action in actions:
                    formatted.append(f"  • {action}")
            else:
                formatted.append(f"• {item}")
        return '\n'.join(formatted)

    return str(content)
