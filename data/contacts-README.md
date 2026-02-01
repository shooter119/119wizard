# 龙游县消防联系人数据库

## 📊 数据概述

本数据库包含龙游县13个乡镇（街道）的消防负责人联系信息，共270条记录。

### 数据统计

- **总记录数**：270条
- **覆盖乡镇**：13个
- **数据完整性**：
  - 电话号码：100%
  - 职务信息：44.1%
  - 行政村名：86.3%

### 各乡镇分布

| 乡镇 | 记录数 |
|------|--------|
| 湖镇镇 | 44条 |
| 龙洲街道 | 40条 |
| 塔石镇 | 28条 |
| 东华街道 | 24条 |
| 詹家镇 | 21条 |
| 石佛乡 | 20条 |
| 横山镇 | 19条 |
| 小南海镇 | 18条 |
| 庙下乡 | 13条 |
| 溪口镇 | 15条 |
| 沐尘乡 | 10条 |
| 罗家乡 | 10条 |
| 社阳乡 | 8条 |

## 📁 数据文件

- **文件路径**：`/Users/vavavoom/Documents/test/data/contacts.json`
- **文件格式**：JSON
- **编码格式**：UTF-8

## 📋 数据结构

每条记录包含以下字段：

```json
{
  "township": "乡镇/街道名称",
  "village": "行政村/社区名称",
  "name": "联系人姓名",
  "phone": "联系电话",
  "position": "职务/岗位",
  "source": "数据来源文件"
}
```

### 字段说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| township | string | 乡镇或街道名称 | "溪口镇" |
| village | string | 行政村或社区名称 | "溪口村" |
| name | string | 联系人姓名 | "陈民强" |
| phone | string | 联系电话（11位手机号） | "13706704751" |
| position | string | 职务或岗位（可选） | "书记" |
| source | string | 数据来源文件名 | "05.溪口镇村干部名录.xlsx" |

## 🔍 数据来源

数据来自以下16个文件：

1. 05.溪口镇村干部名录.xlsx
2. 东华街道各村社消防安全生产负责人名单(1).xlsx
3. 小南海镇各行政村负责消防、安全应急的人员名单.xlsx
4. 庙下乡各村消防负责人.xlsx
5. 罗家乡村干部消防联系人.xlsx
6. 沐尘乡消防人员名单1.xls
7. 石佛乡消防紧急联系人.xlsx
8. 詹家镇各村安全联络员名单.xls
9. 横山镇各村负责人（书记）联系方式.xls
10. 社阳乡各村消防负责人名单.et
11. 模环乡村消防管控责任人清单 (2).et（实际为湖镇镇数据）
12. 塔石镇村志愿消防队名单(1)(1).docx
13. 龙洲街道村社消防安全员名单.docx
14. 龙游县乡镇（街道）自然村汇总表.xlsx
15. 大街乡行政村消防负责人名单.docx（文档为空）
16. 其他补充文件

## 💡 使用示例

### Python 示例

```python
import json

# 读取数据
with open('data/contacts.json', 'r', encoding='utf-8') as f:
    contacts = json.load(f)

# 查询特定乡镇的联系人
def get_contacts_by_township(township_name):
    return [c for c in contacts if c['township'] == township_name]

# 查询特定村的联系人
def get_contacts_by_village(village_name):
    return [c for c in contacts if c['village'] == village_name]

# 根据地址查询联系人
def get_contacts_by_address(address):
    for c in contacts:
        if c['village'] in address or c['township'] in address:
            return c
    return None

# 示例：查询湖镇镇的联系人
huzhen_contacts = get_contacts_by_township('湖镇镇')
print(f"湖镇镇共有{len(huzhen_contacts)}个联系人")
```

### 集成到警情出动提示系统

```python
from test_alert_generation import generate_alert
import json

# 读取联系人数据
with open('data/contacts.json', 'r', encoding='utf-8') as f:
    contacts = json.load(f)

# 查询联系人
def find_contacts(address):
    """根据地址查找相关联系人"""
    results = []
    for contact in contacts:
        # 匹配乡镇
        if contact['township'] in address:
            results.append(contact)
        # 匹配村
        elif contact['village'] and contact['village'] in address:
            results.append(contact)
    return results

# 在警情出动提示中使用
case_data = {
    "address": "浙江省衢州市龙游县湖镇镇新建村环城西路23号",
    # ... 其他字段
}

contacts = find_contacts(case_data['address'])
# 在联动信息章节显示联系人
```

## 🔄 数据更新

### 去重规则

- 以 `乡镇 + 行政村 + 姓名` 作为唯一键
- 重复记录保留电话号码更完整的
- 职务信息会合并（用"、"分隔）

### 数据清洗

- 电话号码统一为11位数字格式
- 科学计数法电话已转换
- 括号中的电话号码已提取
- 空值和无效数据已过滤

## 📝 注意事项

1. **数据时效性**：数据来源于2025-2026年度的联系人名单，建议定期更新

2. **电话格式**：所有电话号码已统一为11位手机号格式

3. **空值处理**：部分记录的行政村或职务字段可能为空

4. **数据来源**：`source`字段记录了数据来源文件，便于追溯

5. **大街乡数据**：大街乡的Word文档内容为空，暂无数据

## 📞 联系方式

如有数据更新或问题，请联系系统管理员。

---

**最后更新**：2026-02-01
**数据版本**：v1.0
**文件位置**：`/Users/vavavoom/Documents/test/data/contacts.json`
