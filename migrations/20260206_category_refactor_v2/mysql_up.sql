-- Category refactor migration (MySQL 8+)
-- Generated from: data/review/category_mapping_final_v2.csv
-- Date tag: 20260206
--
-- Assumptions (adjust before running):
-- 1) Core dictionary table: case_types(id, name, category, subcategory, updated_at)
-- 2) Historical business table: incident_records(case_type_id, case_type_name, category, subcategory)

START TRANSACTION;

CREATE TABLE IF NOT EXISTS category_mapping_v2_20260206 (
    old_id VARCHAR(128) PRIMARY KEY,
    old_name VARCHAR(255) NOT NULL,
    final_primary_category VARCHAR(128) NOT NULL,
    final_subcategory VARCHAR(255) NOT NULL,
    alias_of VARCHAR(128) DEFAULT ''
);

DELETE FROM category_mapping_v2_20260206;

INSERT INTO category_mapping_v2_20260206
(old_id, old_name, final_primary_category, final_subcategory, alias_of)
VALUES
    ('tunnel_fire', '公路隧道火灾', '火灾', '火灾-公路隧道火灾', ''),
    ('chemical_plant_fire', '化工装置企业火灾', '火灾', '火灾-化工装置火灾', ''),
    ('hazmat_transport', '危化品运输车事故', '交通事故', '交通事故-危化品运输车', ''),
    ('kitchen_fire', '厨房火灾', '火灾', '火灾-厨房火灾', ''),
    ('typhoon_disaster', '台风灾害', '救援', '救援-台风灾害', ''),
    ('underground_building_fire', '地下建筑火灾', '火灾', '火灾-地下建筑火灾', ''),
    ('underground_garage_fire', '地下车库火灾', '火灾', '火灾-地下车库火灾', ''),
    ('garbage_fire', '垃圾类火灾', '火灾', '火灾-垃圾类火灾', ''),
    ('multi_storey_building_fire', '多层建筑火灾', '火灾', '火灾-多层建筑火灾', ''),
    ('large_commercial_complex_fire', '大型商业综合体火灾', '火灾', '火灾-大型商业综合体火灾', ''),
    ('large_span_factory', '大跨度厂房火灾', '火灾', '火灾-大跨度厂房火灾', ''),
    ('lab_fire', '实验室火灾', '火灾', '火灾-实验室火灾', ''),
    ('landslide_mudslide', '山体滑坡/泥石流救援', '救援', '救援-地质灾害救援', ''),
    ('mountain_rescue', '山岳救援', '救援', '救援-山岳救援', ''),
    ('construction_site_fire', '工地火灾', '火灾', '火灾-工地火灾', ''),
    ('building_collapse', '建筑物倒塌事故处置', '救援', '救援-建筑物倒塌', ''),
    ('animal_rescue', '抓动物', '救援', '救援-抓动物', ''),
    ('heritage_building_fire', '文物古建筑火灾', '火灾', '火灾-文物古建筑火灾', ''),
    ('vehicle_ev', '新能源汽车火灾', '火灾', '火灾-新能源汽车火灾', ''),
    ('residential_building', '民用建筑火灾', '火灾', '火灾-民用建筑火灾', ''),
    ('water_rescue', '水域营救', '救援', '救援-水域营救', ''),
    ('vehicle_oil_leak', '汽车漏油处置', '救援', '救援-汽车漏油处置', ''),
    ('flood_disaster_rescue', '洪涝灾害救援', '救援', '救援-洪涝灾害救援', ''),
    ('sulfur_leak', '液态硫磺泄漏处置', '救援', '救援-液态硫磺泄漏处置', ''),
    ('ammonia_leak', '液氨泄漏处置', '救援', '救援-液氨泄漏处置', ''),
    ('gas_cylinder_fire', '煤气罐火灾', '火灾', '火灾-煤气罐火灾', ''),
    ('gas_leak', '燃气泄漏处置', '救援', '救援-燃气泄漏处置', ''),
    ('elevator_rescue', '电梯故障救援', '救援', '救援-电梯故障救援', ''),
    ('electrical_equipment_fire', '电气设备火灾', '火灾', '火灾-电气设备火灾', ''),
    ('ebike_fire', '电瓶车火灾', '火灾', '火灾-电瓶车火灾', ''),
    ('waterlogging', '社会救助-内涝抽排水', '社会救助', '社会救助-内涝抽排水', ''),
    ('social_assistance_door', '社会救助-开门', '社会救助', '社会救助-开门', ''),
    ('hornet_removal', '社会救助-摘马蜂窝', '社会救助', '社会救助-摘马蜂窝', ''),
    ('wildland_fire', '草木火灾', '火灾', '火灾-草木火灾', ''),
    ('crush_rescue', '身体部位被卡', '救援', '救援-身体部位被卡', ''),
    ('vehicle_fire', '车辆火灾', '火灾', '火灾-车辆火灾', ''),
    ('traffic_accident_rescue', '道路交通事故救援', '交通事故', '交通事故-道路交通救援', ''),
    ('acetic_acid_leak', '醋酸泄露处置', '救援', '救援-醋酸泄露处置', ''),
    ('high_rise_building', '高层建筑火灾', '火灾', '火灾-高层建筑火灾', ''),
    ('high_altitude_retrieval', '高空取物', '救援', '救援-高空取物', ''),
    ('high_altitude_rescue', '高空救援', '救援', '救援-高空救援', ''),
    ('highway_vehicle_fire', '高速车辆火灾事故', '火灾', '火灾-高速车辆火灾', ''),
    ('lpg_tanker_accident', 'LPG罐车事故', '交通事故', '交通事故-LPG罐车', ''),
    ('lng_tanker_accident', 'LNG罐车事故', '交通事故', '交通事故-LNG罐车', ''),
    ('cng_tanker_accident', 'CNG罐车事故', '交通事故', '交通事故-CNG罐车', '')
;

CREATE TABLE IF NOT EXISTS backup_case_types_20260206 AS
SELECT * FROM case_types;

CREATE TABLE IF NOT EXISTS backup_incident_records_20260206 AS
SELECT * FROM incident_records;

-- 1) Update dictionary table
UPDATE case_types c
JOIN category_mapping_v2_20260206 m ON c.id = m.old_id
SET
    c.category = m.final_primary_category,
    c.subcategory = m.final_subcategory,
    c.updated_at = NOW();

-- 2) Update historical records by id first
UPDATE incident_records i
JOIN category_mapping_v2_20260206 m ON i.case_type_id = m.old_id
SET
    i.category = m.final_primary_category,
    i.subcategory = m.final_subcategory,
    i.case_type_name = m.final_subcategory;

-- 3) Fallback update by old name
UPDATE incident_records i
JOIN category_mapping_v2_20260206 m ON i.case_type_name = m.old_name
SET
    i.category = m.final_primary_category,
    i.subcategory = m.final_subcategory,
    i.case_type_name = m.final_subcategory
WHERE (i.case_type_id IS NULL OR i.case_type_id = '');

COMMIT;
