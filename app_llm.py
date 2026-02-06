#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 灾害类型判定服务（独立于现有脚本）
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge
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
# 上传体大小限制（20MB），与 Nginx client_max_body_size 保持一致。
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
CORS(app)


@app.errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(e):
    return jsonify({
        "success": False,
        "error": "上传文件过大（上限20MB）。请压缩图片后重试。"
    }), 413

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

FIRE_HINT_TERMS = (
    "火灾", "起火", "着火", "冒烟", "燃烧", "阴燃", "明火", "爆燃", "爆炸", "自燃"
)

DOOR_RESCUE_TERMS = (
    "开门", "开锁", "反锁", "门打不开", "忘带钥匙",
    "老人被困", "小孩被困", "被困家中", "室内被困", "困在家里"
)

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

def rank_case_types_by_keywords(text, case_types, top_k=3):
    ranked = []
    for item in case_types:
        name = str(item.get("name") or "").strip()
        aliases = [str(a).strip() for a in (item.get("aliases") or []) if str(a).strip()]
        keywords = [str(k).strip() for k in (item.get("keywords") or []) if str(k).strip()]

        score = 0
        matched_aliases = [a for a in aliases if a in text]
        matched_keywords = [k for k in keywords if k in text]

        if name and name in text:
            score += 10
        score += 6 * len(matched_aliases)
        score += 4 * len(matched_keywords)

        if score <= 0:
            continue

        ranked.append({
            "case_type_id": item.get("id", ""),
            "case_type_name_raw": item.get("name", ""),
            "case_type_name": format_case_type_display(item),
            "case_type_category": item.get("category", ""),
            "case_type_subcategory": item.get("subcategory", ""),
            "score": score,
            "matched_keywords": matched_keywords[:10],
            "matched_aliases": matched_aliases[:6],
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]


def build_keyword_match(text, case_types):
    ranked = rank_case_types_by_keywords(text, case_types, top_k=1)
    if not ranked:
        return None
    best = ranked[0]
    score = best.get("score", 0)
    confidence = min(0.95, 0.45 + score * 0.02)
    return {
        "case_type_id": best.get("case_type_id", ""),
        "case_type_name": best.get("case_type_name", ""),
        "case_type_name_raw": best.get("case_type_name_raw", ""),
        "case_type_category": best.get("case_type_category", ""),
        "case_type_subcategory": best.get("case_type_subcategory", ""),
        "confidence": round(confidence, 2),
        "rationale": "关键词匹配命中",
        "matched_keywords": best.get("matched_keywords", [])
    }


def local_keyword_match(text, case_types):
    return build_keyword_match(text, case_types)

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

def compose_text_from_alert_info(alert_info, include_case_type=True):
    parts = []
    keys = ['station', 'case_level', 'report_time', 'address', 'case_description']
    if include_case_type:
        keys.insert(4, 'case_type')
    for key in keys:
        value = alert_info.get(key, '')
        if value:
            parts.append(str(value))
    return '，'.join(parts)


def _contains_any(text, terms):
    if not text:
        return False
    return any(t in text for t in terms)


def sanitize_alert_info_for_images(alert_info):
    """图片模式下，清洗视觉抽取结果，避免将臆测 case_type 直接喂给分类。"""
    cleaned = dict(alert_info or {})
    desc = str(cleaned.get("case_description") or "")
    addr = str(cleaned.get("address") or "")
    case_type = str(cleaned.get("case_type") or "")
    corpus = f"{desc} {addr}"
    has_fire = _contains_any(corpus, FIRE_HINT_TERMS)
    has_door = _contains_any(corpus, DOOR_RESCUE_TERMS)
    if case_type and ("火" in case_type or "火灾" in case_type) and has_door and not has_fire:
        cleaned["case_type"] = ""
    return cleaned


def apply_image_mode_case_guard(case_obj, match, case_types, extracted_info=None):
    """
    图片模式纠偏：
    若文本体现“开门/被困家中”且无火情词，禁止落到火灾类，强制归到“开门”。
    """
    obj = dict(case_obj or {})
    normalized_match = dict(match or {})
    extracted = extracted_info or {}
    evidence_text = " ".join([
        str(extracted.get("case_description") or ""),
        str(extracted.get("address") or ""),
        str(extracted.get("case_type") or ""),
    ])
    case_text = " ".join([
        str(obj.get("case_description") or ""),
        str(obj.get("address") or ""),
    ])
    has_fire = _contains_any(evidence_text, FIRE_HINT_TERMS)
    has_door = _contains_any(f"{evidence_text} {case_text}", DOOR_RESCUE_TERMS)
    if not (has_door and not has_fire):
        return obj, normalized_match

    door_case = None
    for item in case_types:
        if str(item.get("id") or "") == "social_assistance_door":
            door_case = item
            break
    if not door_case:
        return obj, normalized_match

    matched_keywords = [k for k in (door_case.get("keywords") or []) if k and k in f"{evidence_text} {case_text}"][:6]
    forced = {
        "case_type_id": "social_assistance_door",
        "case_type_name_raw": door_case.get("name", ""),
        "case_type_name": format_case_type_display(door_case),
        "case_type_category": door_case.get("category", ""),
        "case_type_subcategory": door_case.get("subcategory", ""),
        "confidence": 0.88,
        "rationale": "检测到开门/被困家中语义且无火情词，按开门社会救助纠偏",
        "matched_keywords": matched_keywords
    }
    obj["case_type"] = forced["case_type_name"]
    return obj, forced


def apply_image_mode_text_guard(case_obj, extracted_info=None):
    """
    图片模式文本纠偏：
    若截图证据中无火情词，则禁止模型在 case_description 中注入“火灾/起火”等内容。
    """
    obj = dict(case_obj or {})
    extracted = extracted_info or {}
    extracted_desc = str(extracted.get("case_description") or "").strip()
    extracted_case_type = str(extracted.get("case_type") or "").strip()
    evidence_text = f"{extracted_desc} {extracted_case_type}".strip()
    if not evidence_text:
        return obj

    if _contains_any(evidence_text, FIRE_HINT_TERMS):
        return obj

    # 无火情证据时，优先采用截图原始描述，避免模型脑补“火灾”。
    current_desc = str(obj.get("case_description") or "").strip()
    if extracted_desc:
        obj["case_description"] = extracted_desc
    elif _contains_any(current_desc, FIRE_HINT_TERMS):
        # 没有原始描述可回填时，至少去掉显式火情前缀
        cleaned = current_desc
        for term in FIRE_HINT_TERMS:
            cleaned = cleaned.replace(term, "")
        cleaned = re.sub(r'^[，,、\\s]+', '', cleaned).strip()
        obj["case_description"] = cleaned or current_desc
    return obj

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

        if not alert_info:
            return jsonify({"success": False, "error": "截图分析失败：未返回识别结果"}), 500
        if 'error' in alert_info:
            return jsonify({
                "success": False,
                "error": f"截图分析失败：{alert_info.get('error')}"
            }), 500
        if 'parse_error' in alert_info:
            return jsonify({
                "success": False,
                "error": f"截图解析失败：{alert_info.get('parse_error')}"
            }), 500

        # 图片模式：清洗视觉抽取结果，不把抽取到的 case_type 作为强依据
        sanitized_alert_info = sanitize_alert_info_for_images(alert_info)

        # 组装文本并交给 LLM 完成匹配与结构化（不包含 case_type）
        text = compose_text_from_alert_info(sanitized_alert_info, include_case_type=False)
        if not text:
            return jsonify({
                "success": False,
                "error": "未能从截图中提取有效文本，请上传包含“案件详情/出动力量”的清晰截图",
                "alert_info": alert_info,
                "sanitized_alert_info": sanitized_alert_info
            }), 500

        case_types = load_case_types()
        raw = ""

        # 阶段1：如实提取（只使用截图抽取结果构造 case）
        case_obj = merge_case_with_alert_info({}, sanitized_alert_info)
        case_obj = apply_image_mode_text_guard(case_obj, extracted_info=sanitized_alert_info)

        # 阶段2：仅用提取文本做关键词判定
        classify_text = "，".join([
            str(case_obj.get("case_description") or ""),
            str(case_obj.get("address") or "")
        ]).strip("，")
        keyword_hits_top3 = rank_case_types_by_keywords(classify_text, case_types, top_k=3)
        match = build_keyword_match(classify_text, case_types)
        source = "keyword"

        # 关键词无命中时，才使用 LLM 做兜底分类（不允许改写 case_description）
        if not match:
            llm_result, raw = call_llm_classify(classify_text, case_types)
            match = normalize_case_type_match(llm_result or {}, case_types) if llm_result else {}
            if not match:
                match = local_keyword_match(classify_text, case_types) or {}
            source = "llm" if match else "keyword"

        if match.get("case_type_name"):
            case_obj["case_type"] = match.get("case_type_name")

        case_obj, match = apply_image_mode_case_guard(
            case_obj, match, case_types, extracted_info=sanitized_alert_info
        )

        address_match, matched_village = match_address_to_contacts(case_obj.get("address", ""))
        missing = evaluate_completeness(case_obj)
        is_complete = len(missing) == 0

        case_data = build_case_data_from_llm(case_obj, address_match, matched_village)
        alert_text = generate_alert(case_data)

        response_payload = {
            "success": True,
            "source": source,
            "alert": alert_text,
            "case": case_obj,
            "case_type_match": match,
            "keyword_hits_top3": keyword_hits_top3,
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
                "extracted": alert_info,
                "sanitized_extracted": sanitized_alert_info
            },
            "case": case_obj,
            "case_type_match": response_payload["case_type_match"],
            "keyword_hits_top3": keyword_hits_top3,
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
