# 警情类别审核说明

## 文件
- `category_review_full.csv`：全量类别审核表
- `category_review_first30.csv`：首批 30 条样本审核表（建议先审这个）

## 你只需要填写的列
- `status`：`accept` / `revise` / `reject`
- `review_comment`：你的修改意见

## 参考列说明
- `problem_type`：系统初步判断（`啰唆` / `重复` / `模糊` / `可拆分`）
- `suggested_new_primary_category`：建议一级分类
- `suggested_new_subcategory`：建议二级分类
- `alias_of`：若该项是重复项，可填主类的 `old_id`

## 建议审核节奏
1. 先审核 `category_review_first30.csv`
2. 我会根据你的反馈统一规则
3. 再对 `category_review_full.csv` 生成第二版建议
