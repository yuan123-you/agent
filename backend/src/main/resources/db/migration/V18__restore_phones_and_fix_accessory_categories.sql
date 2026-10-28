-- ============================================================================
-- V18: 恢复真实手机整机上架并修正配件类目
-- 1. 确保 mall_category 中存在 DIGITAL (数码配件) 分类
-- 2. 将误归为 PHONE 的各类数码配件修正为 DIGITAL 类目并回填 category_id
-- 3. 恢复基线中的 9 款手机整机商品上架（ID 1-9，含 ¥2999 的星耀 X5 Pro）
-- ============================================================================

-- 1. 确保 mall_category 中存在 DIGITAL 分类
INSERT INTO mall_category (parent_id, name, level, nav_status, show_status, sort)
SELECT 0, 'DIGITAL', 1, 1, 1, 0
WHERE NOT EXISTS (SELECT 1 FROM mall_category WHERE name = 'DIGITAL' AND deleted = 0);

-- 2. 将误归为 PHONE 的各类数码配件修正为 DIGITAL 类目
UPDATE product
SET category = 'DIGITAL'
WHERE category = 'PHONE'
  AND (
    name LIKE '%卡包%' OR name LIKE '%钥匙扣%' OR name LIKE '%耳机%' 
    OR name LIKE '%耳塞%' OR name LIKE '%耳罩%' OR name LIKE '%保护壳%' 
    OR name LIKE '%保护套%' OR name LIKE '%双面夹%' OR name LIKE '%支架%' 
    OR name LIKE '%底座%' OR name LIKE '%充电%' OR name LIKE '%连接线%' 
    OR name LIKE '%转换器%' OR name LIKE '%转接器%' OR name LIKE '%读卡器%' 
    OR name LIKE '%电池%' OR name LIKE '%扩展坞%' OR name LIKE '%Pencil%' 
    OR name LIKE '%清洁套件%' OR name LIKE '%妙控板%' OR name LIKE '%发射器%' 
    OR name LIKE '%扬声器%' OR name LIKE '%手环%' OR name LIKE '%Watch%' 
    OR name LIKE '%手表%' OR name LIKE '%路由器%' OR name LIKE '%键盘%'
  );

-- 回填 DIGITAL 类目关联的 category_id
UPDATE product p
JOIN mall_category c ON c.name = 'DIGITAL' AND c.level = 1 AND c.deleted = 0
SET p.category_id = c.id
WHERE p.category = 'DIGITAL';

-- 3. 恢复基线中的 9 款手机整机商品上架
UPDATE product
SET status = 'ON_SALE', deleted = 0
WHERE id BETWEEN 1 AND 9
  AND category = 'PHONE';

-- 确保恢复的手机商品正确关联分类与品牌
UPDATE product p
JOIN mall_category c ON c.name = 'PHONE' AND c.level = 1 AND c.deleted = 0
SET p.category_id = c.id
WHERE p.id BETWEEN 1 AND 9 AND p.category = 'PHONE';

UPDATE product p
JOIN mall_brand b ON b.name = p.brand AND b.deleted = 0
SET p.brand_id = b.id
WHERE p.id BETWEEN 1 AND 9;
