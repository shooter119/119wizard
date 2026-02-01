#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智谱 GLM-4V 视觉识别模块
功能：从 119 接警系统截图中提取警情信息
"""

from zhipuai import ZhipuAI
import base64
import json
import os

# 获取模块所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 加载配置
def _load_config():
    config_path = os.path.join(BASE_DIR, 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

_CONFIG = _load_config()

# 智谱 API 配置（从 config.json 读取）
ZHIPU_API_KEY = _CONFIG.get('api_keys', {}).get('zhipu', '')

# 初始化客户端
client = ZhipuAI(api_key=ZHIPU_API_KEY)

def encode_image_to_base64(image_path):
    """将图片编码为 Base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def get_mime_type(image_path):
    """获取图片 MIME 类型"""
    ext = os.path.splitext(image_path)[1].lower()
    return {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }.get(ext, 'image/jpeg')

def analyze_screenshot(image_paths):
    """
    使用 GLM-4V 分析 119 接警系统截图
    
    Args:
        image_paths: 图片路径列表
        
    Returns:
        dict: 提取的警情信息
    """
    
    # 构建消息内容
    content = []
    
    # 添加所有图片
    for image_path in image_paths:
        if os.path.exists(image_path):
            base64_image = encode_image_to_base64(image_path)
            mime_type = get_mime_type(image_path)
            
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}"
                }
            })
    
    # 添加提示文字
    content.append({
        "type": "text",
        "text": """请仔细分析这些119消防接警系统的截图，提取所有相关信息。

请以JSON格式返回，格式如下：
```json
{
    "station": "出动消防站名称（如龙游大队永安路站）",
    "case_level": "警情等级（如：一级火灾扑救、一级抢险救援）",
    "report_time": "接警/报警时间（格式：2026年01月12日09时22分）",
    "address": "案发地址（完整地址，如龙游县东华街道下洋村11号）",
    "case_type": "警情类型（如：火灾、民房起火、抢险救援）",
    "case_description": "警情描述（如有人员跳楼、发生火灾等）",
    "vehicles": ["出动车辆列表，包含车牌号"],
    "personnel": 出动总人数,
    "commander": "指挥员姓名",
    "other_members": ["其他出动人员姓名"],
    "reporter_phone": "报警人电话",
    "reporter_name": "报警人姓名"
}
```

注意事项：
1. 只返回JSON，不要有其他说明文字
2. 如果某项信息找不到，设为空字符串""或空数组[]
3. 人数请用数字表示
4. 请仔细查看所有截图中的信息"""
    })
    
    try:
        print("🔍 正在使用 GLM-4V 分析截图...")
        
        response = client.chat.completions.create(
            model="glm-4v-plus",  # 使用 glm-4v-plus 或 glm-4v
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ],
            max_tokens=2000
        )
        
        assistant_message = response.choices[0].message.content
        print(f"📝 模型响应: {assistant_message[:200]}...")
        
        # 尝试解析 JSON
        try:
            # 清理可能的 markdown 代码块标记
            json_str = assistant_message.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1]
            if '```' in json_str:
                json_str = json_str.split('```')[0]
            json_str = json_str.strip()
            
            alert_info = json.loads(json_str)
            print("✅ 截图分析成功！")
            return alert_info
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 解析失败: {e}")
            print(f"原始响应: {assistant_message}")
            # 返回原始文本用于调试
            return {"raw_response": assistant_message, "parse_error": str(e)}
            
    except Exception as e:
        print(f"❌ API 请求异常: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def convert_to_case_data(alert_info):
    """
    将 GLM-4V 提取的信息转换为警情生成器需要的格式
    """
    
    # 处理出动人数
    personnel = alert_info.get('personnel', 0)
    if isinstance(personnel, str):
        try:
            personnel = int(personnel)
        except:
            personnel = 0
    
    # 构建车辆列表（去除车牌号，只保留车型）
    vehicles = alert_info.get('vehicles', [])
    
    # 构建原始警情描述
    station = alert_info.get('station', '')
    case_level = alert_info.get('case_level', '')
    report_time = alert_info.get('report_time', '')
    address = alert_info.get('address', '')
    case_description = alert_info.get('case_description', '')
    
    original_alert = f"{station}警情出动"
    if case_level:
        original_alert += f"（{case_level}）"
    if report_time:
        original_alert += f":{report_time}，"
    original_alert += f"接到报警称:{address}"
    if case_description:
        original_alert += f"，{case_description}"
    
    # 构建人员信息
    commander = alert_info.get('commander', '')
    other_members = alert_info.get('other_members', [])
    
    return {
        'case_number': '',
        'report_time': report_time,
        'case_level': case_level,
        'case_type': alert_info.get('case_type', ''),
        'address': address,
        'station': station,
        'vehicles': vehicles,
        'personnel': personnel,
        'original_alert': original_alert,
        'commander': commander,
        'other_members': other_members,
        'communicator': '',
        'safety_officer': '',
        'comm_equipment': '',
        'reporter_phone': alert_info.get('reporter_phone', ''),
        'reporter_name': alert_info.get('reporter_name', ''),
        'case_description': case_description
    }


# 测试代码
if __name__ == '__main__':
    # 测试分析截图
    screenshot_dir = '/Users/vavavoom/Documents/test/screenshot'
    images = [
        os.path.join(screenshot_dir, '552916e9b57b0feb124b1088342b5864.JPG'),  # 案件详情
        os.path.join(screenshot_dir, '511f3bdd17f40db6debc6e8a133c9c0a.JPG'),  # 出动力量
    ]
    
    print("=" * 60)
    print("🚀 测试 GLM-4V 截图识别")
    print("=" * 60)
    
    result = analyze_screenshot(images)
    
    print("\n📋 识别结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    if 'error' not in result and 'parse_error' not in result:
        case_data = convert_to_case_data(result)
        print("\n📦 转换后的警情数据：")
        print(json.dumps(case_data, ensure_ascii=False, indent=2))
