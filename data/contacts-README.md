# 龙游县消防联系人数据库

## 📊 数据概述

本数据库包含龙游县15个乡镇（街道）的消防负责人联系信息，共286条记录。

### 数据统计

- **总记录数**：286条
- **覆盖乡镇**：15个
- **数据完整性**：
  - 电话号码：100%
  - 职务信息：100%
  - 行政村名：100%

### 各乡镇分布

| 乡镇 | 记录数 |
|------|--------|
| 湖镇镇 | 44条 |
| 龙洲街道 | 33条 |
| 东华街道 | 28条 |
| 塔石镇 | 27条 |
| 詹家镇 | 21条 |
| 模环乡 | 20条 |
| 横山镇 | 20条 |
| 小南海镇 | 18条 |
| 溪口镇 | 15条 |
| 庙下乡 | 13条 |
| 石佛乡 | 11条 |
| 沐尘乡 | 10条 |
| 罗家乡 | 10条 |
| 大街乡 | 8条 |
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

数据来自以下文件：

1. 龙游县乡镇街道负责人.xlsx

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
from alert_generation import generate_alert
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

5. **大街乡数据**：当前数据包含大街乡联系人信息

## 📞 联系方式

如有数据更新或问题，请联系系统管理员。

---

**最后更新**：2026-02-04
**数据版本**：v1.0
**文件位置**：`/Users/vavavoom/Documents/test/data/contacts.json`
