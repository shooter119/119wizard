# 接警信息 → 输出提示 工作流映射（V2 Agent 语义向量库）

本映射基于 `intelligence base/fire_vectors_cleaned_v2_agent.json`，**不改变你现有模板**，仅定义数据检索与内容拼装规则。

## 目标输出（模板保持现状）
- 安全提示
- 处置要点
- 灾害特点
- 作战要则
- 特别警示

## 数据源字段速查
向量条目核心字段：
- `case_id`, `case_name`, `category`
- `knowledge_type`：`handling_point` / `safety_tip` / `characteristic` / `tactic` / `warning`
- `content`：具体文本
- `scenario_tags`, `risk_tags`, `equipment_tags`
- `priority`（normal/critical）
- `tactical_phase`（准备阶段/态势研判阶段/处置阶段/作战阶段/风险控制阶段）
- `decision_role`（指挥员决策参考/战斗组执行参考/通用知识参考）
- `risk_level_estimated`（数值风险等级）

## 工作流映射（建议实现顺序）
1. **接警文本结构化**
   - 现状：`/api/llm-analyze` 或 `/api/llm-generate` 已输出 `case_type_name`、`case_description` 等字段。

2. **灾害类型确定**
   - 使用现有灾害类型库（`fire_cases_complete.json`）完成匹配。
   - 输出 `case_type_name` / `case_type_id` 作为主检索条件。

3. **V2 语义向量检索**
   - 精准匹配（优先级最高）：`case_id == case_type_id` 或 `case_name == case_type_name`。
   - 语义召回（兜底）：
     - `scenario_tags`、`risk_tags` 中包含灾害类型名/关键词。
     - `case_description` 做向量检索或关键词匹配。

4. **分区聚合 → 现有模板字段**
   - `knowledge_type = safety_tip` → 安全提示
   - `knowledge_type = handling_point` → 处置要点
   - `knowledge_type = characteristic` → 灾害特点
   - `knowledge_type = tactic` → 作战要则
   - `knowledge_type = warning` → 特别警示

5. **排序与裁剪（保证输出稳定）**
   - 先按 `priority`（critical > normal）排序
   - 再按 `risk_level_estimated` 从高到低
   - 再按 `decision_role`（指挥员 > 战斗组 > 通用）
   - 最后按 `tactical_phase` 与输出区块匹配度
   - 每类取 Top N（建议 5~8 条）

6. **模板填充（保持现状）**
   - 将每类文本列表直接喂给当前模板输出（不变更结构/格式）。

## 输出区块与战术阶段推荐映射（可选）
- 安全提示：优先 `准备阶段` / `风险控制阶段`
- 处置要点：优先 `处置阶段`
- 灾害特点：优先 `态势研判阶段`
- 作战要则：优先 `作战阶段`
- 特别警示：优先 `风险控制阶段`

## 兜底策略
- 若某一类为空：
  - 使用 `case_description` 做语义检索补充
  - 或跨 `category` 相近灾害类型补充（同类别）
- 若仍为空：
  - 保留模板标题，仅输出 1 行“暂无专门条目”提示（保持模板结构）

---

如需我把这份映射落到具体代码（比如 `app_llm.py` 或新建 RAG 处理脚本），告诉我你希望的落点即可。
