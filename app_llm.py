#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 灾害类型判定服务（独立于现有脚本）
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import re
from datetime import datetime
import tempfile

from alert_generation import generate_alert, validate_and_correct_address
from glm_vision import analyze_screenshot

try:
    from zhipuai import ZhipuAI
except Exception:
    ZhipuAI = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_config():
    config_path = os.path.join(BASE_DIR, 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

_CONFIG = _load_config()
ZHIPU_API_KEY = _CONFIG.get('api_keys', {}).get('zhipu', '')

app = Flask(__name__)
CORS(app)

def load_case_types():
    case_path = os.path.join(BASE_DIR, 'data', 'fire_cases_complete.json')
    with open(case_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('case_types', [])

def load_contacts_villages():
    contacts_path = os.path.join(BASE_DIR, 'data', 'contacts.json')
    try:
        with open(contacts_path, 'r', encoding='utf-8') as f:
            items = json.load(f)
        villages = set()
        for item in items:
            name = (item.get('village') or '').strip()
            if len(name) >= 2:
                villages.add(name)
        return villages
    except Exception:
        return set()

CONTACT_VILLAGES = load_contacts_villages()

LOG_PATH = os.path.join(BASE_DIR, 'data', 'llm_logs.jsonl')

def log_llm_event(payload):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass

def build_case_type_catalog(case_types, max_keywords=8):
    catalog = []
    for item in case_types:
        catalog.append({
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "display_name": format_case_type_display(item),
            "category": item.get("category", ""),
            "subcategory": item.get("subcategory", ""),
            "aliases": item.get("aliases", [])[:5],
            "keywords": item.get("keywords", [])[:max_keywords]
        })
    return catalog

def format_case_type_display(item):
    subcategory = (item.get("subcategory") or "").strip()
    if subcategory:
        return subcategory
    category = (item.get("category") or "").strip()
    name = (item.get("name") or "").strip()
    if category and name:
        return f"{category}-{name}"
    return name

def normalize_case_type_match(match, case_types):
    if not isinstance(match, dict):
        return {}

    by_id = {str(item.get("id", "")): item for item in case_types}
    by_name = {}
    for item in case_types:
        names = {
            str(item.get("name", "")).strip(),
            str(item.get("subcategory", "")).strip(),
            format_case_type_display(item).strip(),
        }
        for alias in item.get("aliases") or []:
            names.add(str(alias).strip())
        for n in names:
            if n:
                by_name[n] = item

    picked = None
    case_type_id = str(match.get("case_type_id", "")).strip()
    case_type_name = str(match.get("case_type_name", "")).strip()
    if case_type_id and case_type_id in by_id:
        picked = by_id[case_type_id]
    elif case_type_name and case_type_name in by_name:
        picked = by_name[case_type_name]

    normalized = dict(match)
    if picked:
        normalized["case_type_id"] = picked.get("id", "")
        normalized["case_type_name_raw"] = picked.get("name", "")
        normalized["case_type_name"] = format_case_type_display(picked)
        normalized["case_type_category"] = picked.get("category", "")
        normalized["case_type_subcategory"] = picked.get("subcategory", "")
    return normalized

def local_keyword_match(text, case_types):
    best = None
    best_score = 0
    for item in case_types:
        name = item.get("name", "")
        aliases = item.get("aliases") or []
        keywords = item.get("keywords") or []
        score = 0
        if name and name in text:
            score += 6
        score += sum(3 for a in aliases if a and a in text)
        score += sum(2 for k in keywords if k and k in text)
        if score > best_score:
            best_score = score
            best = item
    if not best:
        return None
    return {
        "case_type_id": best.get("id", ""),
        "case_type_name": format_case_type_display(best),
        "case_type_name_raw": best.get("name", ""),
        "case_type_category": best.get("category", ""),
        "case_type_subcategory": best.get("subcategory", ""),
        "confidence": 0.45,
        "rationale": "本地关键词匹配兜底",
        "matched_keywords": [k for k in (best.get("keywords") or []) if k in text]
    }

def parse_llm_json(raw):
    if not raw:
        return None
    cleaned = raw.strip()
    if '```json' in cleaned:
        cleaned = cleaned.split('```json', 1)[1]
    if '```' in cleaned:
        cleaned = cleaned.split('```', 1)[0]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return None

def repair_llm_json(raw, schema_hint=""):
    if not ZHIPU_API_KEY or not ZhipuAI:
        return None
    if not raw:
        return None
    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    system_prompt = "你是JSON修复器。只输出JSON，不要输出其他文字。"
    user_prompt = {
        "raw_output": raw,
        "schema_hint": schema_hint or ""
    }
    response = client.chat.completions.create(
        model="glm-4-plus",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)}
        ],
        max_tokens=800
    )
    content = response.choices[0].message.content
    return parse_llm_json(content)

def compose_text_from_alert_info(alert_info):
    parts = []
    for key in ['station', 'case_level', 'report_time', 'address', 'case_type', 'case_description']:
        value = alert_info.get(key, '')
        if value:
            parts.append(str(value))
    return '，'.join(parts)

def merge_case_with_alert_info(case_obj, alert_info):
    merged = dict(case_obj or {})
    fields = [
        'station', 'case_level', 'report_time', 'address',
        'case_description', 'vehicles', 'personnel', 'commander',
        'other_members', 'reporter_phone', 'reporter_name'
    ]
    for key in fields:
        value = merged.get(key)
        if not value:
            merged[key] = alert_info.get(key, merged.get(key, ''))
    return merged

def call_llm_classify(text, case_types):
    if not ZHIPU_API_KEY or not ZhipuAI:
        return None, "未配置智谱 API Key 或 SDK"

    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    catalog = build_case_type_catalog(case_types)

    system_prompt = (
        "你是消防警情分拣助手。"
        "必须从给定的灾害类型列表中选择最匹配的一项。"
        "只输出JSON，不要输出其他文字。"
    )

    user_prompt = {
        "text": text,
        "case_types": catalog,
        "output_schema": {
            "case_type_id": "必须来自列表中的id",
            "case_type_name": "必须来自列表中的name",
            "confidence": "0-1之间的小数",
            "rationale": "简短理由",
            "matched_keywords": ["可选，命中的关键词或短语"]
        }
    }

    response = client.chat.completions.create(
        model="glm-4-plus",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)}
        ],
        max_tokens=800
    )
    content = response.choices[0].message.content
    parsed = parse_llm_json(content)
    return parsed, content

def call_llm_extract(text, case_types):
    if not ZHIPU_API_KEY or not ZhipuAI:
        return None, "未配置智谱 API Key 或 SDK"

    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    catalog = build_case_type_catalog(case_types)

    system_prompt = (
        "你是消防警情结构化助手。"
        "必须从给定的灾害类型列表中选择最匹配的一项。"
        "只输出JSON，不要输出其他文字。"
    )

    user_prompt = {
        "text": text,
        "case_types": catalog,
        "output_schema": {
            "case": {
                "station": "出动消防站名称",
                "case_level": "警情等级",
                "report_time": "接警/报警时间（如：2026年01月12日09时22分）",
                "address": "案发地址（完整地址）",
                "case_type": "灾害类型名称（必须在列表中）",
                "case_description": "警情描述",
                "vehicles": ["出动车辆列表"],
                "personnel": "出动总人数（数字）",
                "commander": "指挥员姓名",
                "other_members": ["其他出动人员姓名"],
                "reporter_phone": "报警人电话",
                "reporter_name": "报警人姓名"
            },
            "case_type_match": {
                "case_type_id": "必须来自列表中的id",
                "case_type_name": "必须来自列表中的name",
                "confidence": "0-1之间的小数",
                "rationale": "简短理由",
                "matched_keywords": ["可选，命中的关键词或短语"]
            }
        }
    }

    response = client.chat.completions.create(
        model="glm-4-plus",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)}
        ],
        max_tokens=1200
    )
    content = response.choices[0].message.content
    parsed = parse_llm_json(content)
    if parsed is None:
        schema_hint = json.dumps(user_prompt.get("output_schema", {}), ensure_ascii=False)
        repaired = repair_llm_json(content, schema_hint=schema_hint)
        if repaired is not None:
            return repaired, content
    return parsed, content

def evaluate_completeness(case_obj):
    required_fields = [
        "station",
        "case_level",
        "report_time",
        "address",
        "case_type",
        "case_description",
        "vehicles",
        "personnel",
        "commander"
    ]
    missing = []
    for field in required_fields:
        value = case_obj.get(field)
        if field == "vehicles":
            if not isinstance(value, list) or len(value) == 0:
                missing.append(field)
        elif field == "personnel":
            try:
                if value is None or int(value) <= 0:
                    missing.append(field)
            except Exception:
                missing.append(field)
        else:
            if not value:
                missing.append(field)
    return missing

def match_address_to_contacts(address):
    if not address:
        return False, ''
    corrected_address, _ = validate_and_correct_address(str(address))
    cleaned = re.sub(r'\s+', '', corrected_address)
    if not cleaned:
        return False, ''
    for name in sorted(CONTACT_VILLAGES, key=len, reverse=True):
        if name in cleaned:
            return True, name
    return False, ''

def build_case_data_from_llm(case_obj, address_match=False, matched_village=''):
    station = case_obj.get('station', '')
    case_level = case_obj.get('case_level', '')
    report_time = case_obj.get('report_time', '')
    address = case_obj.get('address', '')
    case_description = case_obj.get('case_description', '')
    case_type = case_obj.get('case_type', '')
    vehicles = case_obj.get('vehicles', []) or []
    personnel = case_obj.get('personnel', 0)
    try:
        personnel = int(personnel)
    except Exception:
        personnel = 0

    original_alert = f"{station}警情出动"
    if case_level:
        original_alert += f"（{case_level}）"
    if report_time:
        original_alert += f":{report_time}，"
    original_alert += f"接到报警称:{address}"
    if case_description:
        original_alert += f"，{case_description}"

    return {
        'case_number': '',
        'report_time': report_time,
        'case_level': case_level,
        'case_type': case_type,
        'address': address,
        'station': station,
        'vehicles': vehicles,
        'personnel': personnel,
        'original_alert': original_alert,
        'commander': case_obj.get('commander', ''),
        'communicator': '',
        'safety_officer': '',
        'comm_equipment': '',
        'driver': '',
        'other_members': case_obj.get('other_members', []) or [],
        '_address_match': bool(address_match),
        '_matched_village': matched_village
    }

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'page_llm.html')

@app.route('/cases')
def cases_page():
    return send_from_directory(BASE_DIR, 'cases.html')

@app.route('/contacts')
def contacts_page():
    return send_from_directory(BASE_DIR, 'contacts.html')

@app.route('/data/<path:filename>')
def data_files(filename):
    data_dir = os.path.join(BASE_DIR, 'data')
    return send_from_directory(data_dir, filename)

@app.route('/api/case-types', methods=['GET'])
def case_types_api():
    case_list = []
    try:
        case_path = os.path.join(BASE_DIR, 'data', 'fire_cases_complete.json')
        with open(case_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for item in data.get('case_types', []):
            case_list.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "display_name": format_case_type_display(item),
                "category": item.get("category", ""),
                "subcategory": item.get("subcategory", ""),
                "aliases": item.get("aliases", []),
                "keywords": item.get("keywords", []),
                "priority": item.get("priority", ""),
                "content": item.get("content", {})
            })
    except Exception:
        case_list = []

    return jsonify({
        "success": True,
        "count": len(case_list),
        "cases": case_list
    })

@app.route('/api/case-types/save', methods=['POST'])
def case_types_save():
    try:
        payload = request.get_json(force=True) or {}
        cases = payload.get("cases")
        if not isinstance(cases, list):
            return jsonify({"success": False, "error": "cases 必须是数组"}), 400

        normalized = []
        for item in cases:
            if not isinstance(item, dict):
                continue
            case_id = (item.get("id") or "").strip()
            name = (item.get("name") or "").strip()
            if not case_id or not name:
                return jsonify({"success": False, "error": "每条必须包含 id 和 name"}), 400
            normalized.append({
                "id": case_id,
                "name": name,
                "category": (item.get("category") or "").strip(),
                "subcategory": (item.get("subcategory") or "").strip(),
                "aliases": item.get("aliases") or [],
                "keywords": item.get("keywords") or [],
                "priority": (item.get("priority") or "").strip(),
                "content": item.get("content") or {}
            })

        case_path = os.path.join(BASE_DIR, 'data', 'fire_cases_complete.json')
        backup_path = case_path + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            if os.path.exists(case_path):
                with open(case_path, 'r', encoding='utf-8') as f:
                    original = f.read()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(original)
        except Exception:
            pass

        data = {
            "version": "local",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "local_editor",
            "description": "local updated",
            "total_cases": len(normalized),
            "case_types": normalized
        }
        with open(case_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True, "count": len(normalized)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/llm-classify', methods=['POST'])
def llm_classify():
    try:
        payload = request.get_json(force=True) or {}
        text = (payload.get('text') or '').strip()
        if not text:
            return jsonify({"success": False, "error": "请输入警情描述文字"}), 400

        case_types = load_case_types()
        llm_result, raw = call_llm_classify(text, case_types)

        if llm_result:
            llm_result = normalize_case_type_match(llm_result, case_types)
            return jsonify({
                "success": True,
                "source": "llm",
                "result": llm_result,
                "raw": raw
            })

        fallback = local_keyword_match(text, case_types)
        if fallback:
            return jsonify({
                "success": True,
                "source": "fallback",
                "result": fallback,
                "raw": raw or ""
            })

        return jsonify({
            "success": False,
            "error": "模型无有效响应，且本地匹配为空",
            "raw": raw or ""
        }), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/llm-analyze', methods=['POST'])
def llm_analyze():
    try:
        payload = request.get_json(force=True) or {}
        text = (payload.get('text') or '').strip()
        if not text:
            return jsonify({"success": False, "error": "请输入警情描述文字"}), 400

        case_types = load_case_types()
        llm_result, raw = call_llm_extract(text, case_types)

        if not llm_result or not isinstance(llm_result, dict):
            return jsonify({"success": False, "error": "模型无有效JSON输出", "raw": raw or ""}), 500

        case_obj = llm_result.get("case") or {}
        match = normalize_case_type_match(llm_result.get("case_type_match") or {}, case_types)
        if match.get("case_type_name"):
            case_obj["case_type"] = match.get("case_type_name")
        address_match, matched_village = match_address_to_contacts(case_obj.get("address", ""))
        missing = evaluate_completeness(case_obj)
        is_complete = len(missing) == 0

        return jsonify({
            "success": True,
            "source": "llm",
            "case": case_obj,
            "case_type_match": match,
            "is_complete": is_complete,
            "missing_fields": missing,
            "address_match": address_match,
            "matched_village": matched_village,
            "raw": raw or ""
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/llm-generate', methods=['POST'])
def llm_generate():
    try:
        payload = request.get_json(force=True) or {}
        text = (payload.get('text') or '').strip()
        if not text:
            return jsonify({"success": False, "error": "请输入警情描述文字"}), 400

        case_types = load_case_types()
        llm_result, raw = call_llm_extract(text, case_types)

        if not llm_result or not isinstance(llm_result, dict):
            return jsonify({"success": False, "error": "模型无有效JSON输出", "raw": raw or ""}), 500

        case_obj = llm_result.get("case") or {}
        match = normalize_case_type_match(llm_result.get("case_type_match") or {}, case_types)
        if match.get("case_type_name"):
            case_obj["case_type"] = match.get("case_type_name")
        address_match, matched_village = match_address_to_contacts(case_obj.get("address", ""))
        missing = evaluate_completeness(case_obj)
        is_complete = len(missing) == 0

        case_data = build_case_data_from_llm(case_obj, address_match, matched_village)
        alert_text = generate_alert(case_data)

        response_payload = {
            "success": True,
            "source": "llm",
            "alert": alert_text,
            "case": case_obj,
            "case_type_match": match,
            "is_complete": is_complete,
            "missing_fields": missing,
            "address_match": address_match,
            "matched_village": matched_village,
            "raw": raw or ""
        }

        log_llm_event({
            "timestamp": datetime.now().isoformat(timespec='seconds'),
            "mode": "text",
            "input": text,
            "case": case_obj,
            "case_type_match": response_payload["case_type_match"],
            "is_complete": is_complete,
            "missing_fields": missing,
            "address_match": address_match,
            "matched_village": matched_village,
            "amap_raw": case_data.get("_geocode_raw"),
            "amap_used": case_data.get("_geocode_used"),
            "alert": alert_text,
            "raw": raw or ""
        })

        return jsonify(response_payload)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/llm-generate-images', methods=['POST'])
def llm_generate_images():
    temp_paths = []
    try:
        if 'images' not in request.files:
            return jsonify({"success": False, "error": "请上传截图文件"}), 400

        files = request.files.getlist('images')
        if not files:
            return jsonify({"success": False, "error": "请上传至少一张截图"}), 400
        if len(files) > 3:
            return jsonify({"success": False, "error": "最多上传3张照片"}), 400

        for file in files:
            if file.filename:
                ext = os.path.splitext(file.filename)[1] or '.jpg'
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                try:
                    file.save(temp_file.name)
                finally:
                    temp_file.close()
                temp_paths.append(temp_file.name)

        alert_info = analyze_screenshot(temp_paths)

        if not alert_info or 'error' in alert_info:
            return jsonify({"success": False, "error": "截图分析失败"}), 500
        if 'parse_error' in alert_info:
            return jsonify({"success": False, "error": "截图解析失败"}), 500

        # 组装文本并交给 LLM 完成匹配与结构化
        text = compose_text_from_alert_info(alert_info)
        if not text:
            return jsonify({"success": False, "error": "未能从截图中提取有效文本"}), 500

        case_types = load_case_types()
        llm_result, raw = call_llm_extract(text, case_types)
        if not llm_result or not isinstance(llm_result, dict):
            return jsonify({"success": False, "error": "模型无有效JSON输出", "raw": raw or ""}), 500

        case_obj = llm_result.get("case") or {}
        case_obj = merge_case_with_alert_info(case_obj, alert_info)
        match = normalize_case_type_match(llm_result.get("case_type_match") or {}, case_types)
        if match.get("case_type_name"):
            case_obj["case_type"] = match.get("case_type_name")

        address_match, matched_village = match_address_to_contacts(case_obj.get("address", ""))
        missing = evaluate_completeness(case_obj)
        is_complete = len(missing) == 0

        case_data = build_case_data_from_llm(case_obj, address_match, matched_village)
        alert_text = generate_alert(case_data)

        response_payload = {
            "success": True,
            "source": "llm",
            "alert": alert_text,
            "case": case_obj,
            "case_type_match": match,
            "is_complete": is_complete,
            "missing_fields": missing,
            "address_match": address_match,
            "matched_village": matched_village,
            "raw": raw or ""
        }

        log_llm_event({
            "timestamp": datetime.now().isoformat(timespec='seconds'),
            "mode": "images",
            "input": {
                "images": [os.path.basename(p) for p in temp_paths],
                "extracted": alert_info
            },
            "case": case_obj,
            "case_type_match": response_payload["case_type_match"],
            "is_complete": is_complete,
            "missing_fields": missing,
            "address_match": address_match,
            "matched_village": matched_village,
            "amap_raw": case_data.get("_geocode_raw"),
            "amap_used": case_data.get("_geocode_used"),
            "alert": alert_text,
            "raw": raw or ""
        })

        return jsonify(response_payload)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        # Ensure temp uploads are always removed, even on analyze/LLM exceptions.
        for p in temp_paths:
            try:
                os.remove(p)
            except Exception:
                pass

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 LLM 灾害类型判定服务")
    print("=" * 60)
    print("📝 访问地址：http://localhost:5002")
    print("⚠️  按 Ctrl+C 停止服务器")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5002, debug=False)
