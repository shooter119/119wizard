# 119Wizard 警情出动提示系统

基于 Python Flask 的消防警情智能辅助系统，支持：
- 截图识别（GLM-4V）
- 地址解析与路径规划（高德地图）
- 实时天气获取（和风天气）
- 灾害类型匹配与结构化提取（LLM + 本地关键词兜底）
- 战术处置要点生成

## 快速开始

```bash
python3 app_llm.py
# 访问 http://localhost:5002
```

或使用脚本：

```bash
./start-server.sh
```

## 项目结构

```text
├── app_llm.py                   # Flask 主服务（当前入口）
├── alert_generation.py          # 警情提示生成
├── glm_vision.py                # 截图识别
├── unit_type_detector.py        # 单位类型识别
├── page_llm.html                # 主页面
├── cases.html                   # 案例类型管理页
├── contacts.html                # 联系人管理页
├── config.json                  # API 配置
├── data/
│   ├── fire_cases_complete.json
│   ├── contacts.json
│   ├── vehicles.json
│   └── station_coordinates_quzhou.json
└── tests/
```

## 配置说明

在 `config.json` 中配置 API 密钥：
- `amap`: 高德地图 API
- `qweather`: 和风天气 API
- `zhipu`: 智谱 API

## 测试

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## 许可证

MIT License
