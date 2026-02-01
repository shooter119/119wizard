#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
警情出动提示生成测试服务器 - 截图识别版
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sys
import os
import tempfile
import re

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from test_alert_generation import generate_alert
from glm_vision import analyze_screenshot, convert_to_case_data

app = Flask(__name__)
CORS(app)  # 允许跨域请求


def parse_alert_text(text):
    """解析警情描述文字，提取关键信息"""
    
    result = {
        'case_number': '',
        'report_time': '',
        'case_level': '',
        'case_type': '',
        'address': '',
        'station': '',
        'vehicles': [],
        'personnel': 0,
        'original_alert': '',
        'commander': '',
        'communicator': '',
        'safety_officer': '',
        'comm_equipment': '',
        'driver': '',
        'other_members': []
    }

    # 按行分割文本，第一行作为原始警情描述
    lines = text.strip().split('\n')
    result['full_text'] = text  # 保存完整文本以供进一步分析
    if lines:
        result['original_alert'] = lines[0].strip()

    # 提取消防站名称
    station_match = re.search(r'([\u4e00-\u9fa5]+站)', text)
    if station_match:
        result['station'] = station_match.group(1)

    # 提取警情等级
    level_match = re.search(r'（([一二三四]级[\u4e00-\u9fa5]+)）', text)
    if level_match:
        result['case_level'] = level_match.group(1)

    # 提取报警时间
    time_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日\d{1,2}时\d{1,2}分)', text)
    if time_match:
        result['report_time'] = time_match.group(1)

    # 提取地址
    address_patterns = [
        r'龙游县[^，。]+?(?:街道|镇|乡|村|社区|路|大道|巷|号|小区|大厦|栋)[^，。]*?(?=[，。]|$)',
        r'称[：:]\s*([^，。]+?)(?:，|。|发生|起火|有人员)',
        # 新增：匹配常见行政区域结构，如 "XX县XX乡XX村"
        r'([\u4e00-\u9fa5]+(?:县|区|市|镇|乡|村|路|街)[\u4e00-\u9fa5]+?(?=起火|发生|有人员|，|。))'
    ]
    for pattern in address_patterns:
        addr_match = re.search(pattern, text)
        if addr_match:
            addr = addr_match.group(1) if addr_match.lastindex else addr_match.group(0)
            result['address'] = addr.strip()
            break

    # 提取案件类型
    if '火灾' in text or '起火' in text or '冒烟' in text:
        if '高层' in text:
            result['case_type'] = '高层建筑火灾'
        elif '民房' in text or '住宅' in text:
            result['case_type'] = '民房起火'
        elif '厨房' in text:
            result['case_type'] = '厨房火灾'
        elif any(kw in text for kw in ['车辆', '汽车', '货车', '小车', '轿车', '客车', '面包车']):
            result['case_type'] = '车辆火灾'
        else:
            # 默认使用民用建筑火灾（适用于小作坊、店铺等）
            result['case_type'] = '民用建筑火灾'
    elif '跳楼' in text or '轻生' in text or '天台' in text:
        result['case_type'] = '高空救援'
    elif '车祸' in text or '交通事故' in text:
        result['case_type'] = '车祸救援'
    elif '电梯' in text and '困' in text:
        result['case_type'] = '电梯困人'
    elif any(kw in text for kw in ['卡', '夹', '挤压']):
        result['case_type'] = '身体部位被卡'
    elif '马蜂' in text or '蜂窝' in text:
        result['case_type'] = '摘马蜂窝'
    elif any(kw in text for kw in ['落水', '溺水', '溺', '水域']):
        result['case_type'] = '水域救援'
    elif '开门' in text or '破门' in text:
        result['case_type'] = '开门求助'
    elif '抢险救援' in text:
        result['case_type'] = '抢险救援'
    elif '社会救助' in text:
        result['case_type'] = '社会救助'
    else:
        result['case_type'] = '警情处置'

    # 提取出动车辆和人数 (灵活匹配多种格式)
    # 格式1: 出动2车10人（A车、B车）
    v_match1 = re.search(r'出动(\d+)车(\d+)人[（(]([^）\)]+)[）\)]', text)
    # 格式2: 出动2车（A车、B车）10人
    v_match2 = re.search(r'出动(\d+)车[（(]([^）\)]+)[）\)](\d+)人', text)
    
    if v_match1:
        result['personnel'] = int(v_match1.group(2))
        vehicles_str = v_match1.group(3)
        result['vehicles'] = [v.strip() for v in vehicles_str.split('、') if v.strip()]
    elif v_match2:
        result['personnel'] = int(v_match2.group(3))
        vehicles_str = v_match2.group(2)
        result['vehicles'] = [v.strip() for v in vehicles_str.split('、') if v.strip()]
    else:
        # 兜底：只匹配车和人
        v_match3 = re.search(r'(\d+)车(\d+)人', text)
        if v_match3:
            result['personnel'] = int(v_match3.group(2))
        
        # 尝试单独提取括号里的车辆列表
        v_list_match = re.search(r'[（\(]([^）\)]*?[\u4e00-\u9fa5]车[^）\)]*?)[）\)]', text)
        if v_list_match:
            vehicles_str = v_list_match.group(1)
            result['vehicles'] = [v.strip() for v in vehicles_str.split('、') if v.strip()]

    # 提取指挥员
    commander_match = re.search(r'指挥员[：:]\s*([\u4e00-\u9fa5]+)\s*(\d{11})?', text)
    if commander_match:
        name = commander_match.group(1).strip()
        phone = commander_match.group(2) or ''
        result['commander'] = f"{name} {phone}".strip()

    # 提取通信员
    communicator_match = re.search(r'通信员[：:]\s*([\u4e00-\u9fa5]+)\s*(\d{11})?', text)
    if communicator_match:
        name = communicator_match.group(1).strip()
        phone = communicator_match.group(2) or ''
        result['communicator'] = f"{name} {phone}".strip()

    # 提取安全员
    safety_match = re.search(r'安全员[：:]\s*([\u4e00-\u9fa5]+)\s*(\d{11})?', text)
    if safety_match:
        name = safety_match.group(1).strip()
        phone = safety_match.group(2) or ''
        result['safety_officer'] = f"{name} {phone}".strip()

    # 提取通信装备
    comm_match = re.search(r'携带通信装备[：:]\s*([^。\n]+)', text)
    if comm_match:
        result['comm_equipment'] = comm_match.group(1).strip()

    return result

@app.route('/')
def index():
    """返回测试页面"""
    return send_from_directory(BASE_DIR, 'test_page.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """分析上传的截图并生成警情提示"""
    try:
        # 检查是否有文件上传
        if 'images' not in request.files:
            return jsonify({
                'success': False,
                'error': '请上传截图文件'
            })
        
        files = request.files.getlist('images')
        if not files or len(files) == 0:
            return jsonify({
                'success': False,
                'error': '请上传至少一张截图'
            })
        
        # 保存上传的文件到临时目录
        temp_paths = []
        for file in files:
            if file.filename:
                # 创建临时文件
                ext = os.path.splitext(file.filename)[1] or '.jpg'
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                file.save(temp_file.name)
                temp_paths.append(temp_file.name)
                print(f"📁 保存临时文件: {temp_file.name}")
        
        if not temp_paths:
            return jsonify({
                'success': False,
                'error': '没有有效的图片文件'
            })
        
        # 使用 GLM-4V 分析截图
        print(f"🔍 开始分析 {len(temp_paths)} 张截图...")
        alert_info = analyze_screenshot(temp_paths)
        
        # 清理临时文件
        for path in temp_paths:
            try:
                os.unlink(path)
            except:
                pass
        
        # 检查分析结果
        if 'error' in alert_info:
            return jsonify({
                'success': False,
                'error': f"截图分析失败: {alert_info['error']}"
            })
        
        if 'parse_error' in alert_info:
            return jsonify({
                'success': False,
                'error': f"解析失败: {alert_info.get('raw_response', '')}"
            })
        
        # 转换为警情数据格式
        case_data = convert_to_case_data(alert_info)
        
        # 生成警情提示
        alert = generate_alert(case_data)
        
        return jsonify({
            'success': True,
            'result': alert,
            'extracted_info': alert_info  # 同时返回提取的原始信息
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/generate', methods=['POST'])
def generate():
    """生成警情出动提示（文本输入方式）"""
    try:
        data = request.json
        text = data.get('text', '')

        if not text:
            return jsonify({
                'success': False,
                'error': '请提供警情描述文字'
            })

        # 解析警情文本
        case_data = parse_alert_text(text)

        # 生成提示
        alert = generate_alert(case_data)

        return jsonify({
            'success': True,
            'result': alert
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })


if __name__ == '__main__':
    print("="*60)
    print("🚀 警情出动提示生成测试服务器 - 截图识别版")
    print("="*60)
    print("📝 访问地址：http://localhost:5001")
    print("� 支持功能：上传截图自动识别")
    print("⚠️  按 Ctrl+C 停止服务器")
    print("="*60)
    print()

    app.run(host='0.0.0.0', port=5001, debug=False)
