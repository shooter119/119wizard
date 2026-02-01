# 119 警情出动提示系统

基于 Python Flask 的消防警情智能辅助系统，支持：
- 📸 截图识别（GLM-4V）
- 🗺️ 地址解析与路径规划（高德地图）
- 🌤️ 实时天气获取（和风天气）
- 🏭 单位类型智能识别
- 📋 战术处置要点生成

## 快速开始

```bash
# 启动服务
python3 test_app.py

# 访问 http://localhost:5001
```

## 项目结构

```
├── config.json              # 配置文件（API 密钥）
├── test_app.py              # Flask 主服务器
├── test_alert_generation.py # 核心警情生成逻辑
├── unit_type_detector.py    # 单位类型检测器
├── glm_vision.py            # GLM-4V 截图识别
├── test_page.html           # 前端测试页面
└── data/                    # 数据目录
    ├── contacts.json        # 联系人数据库
    ├── fire_cases_complete.json  # 处置方案数据库
    ├── station_coordinates_quzhou.json  # 消防站坐标
    └── vehicles.json        # 车辆数据库
```

## 配置说明

在 `config.json` 中配置 API 密钥：
- `amap`: 高德地图 API
- `qweather`: 和风天气 API
- `zhipu`: 智谱 GLM-4V API

## 许可证

MIT License
