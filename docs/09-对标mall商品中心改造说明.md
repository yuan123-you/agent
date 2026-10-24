# 09 - 对标 mall 的商城目录改造说明

> 改造日期：2026-10-24。对标项目：[macrozheng/mall](https://github.com/macrozheng/mall)（84.9k★，Apache-2.0）。
> 范围：商城目录中心（分类 / 品牌 / SKU）。**AI 智能客服（ai-service、chat、kb、internal、workbench）零改动。**

## 一、为什么选 mall 作为模板

| 候选 | Stars | 技术栈 | 结论 |
| --- | --- | --- | --- |
| **macrozheng/mall** | 84.9k | Spring Boot + MyBatis + MySQL + Redis + Vue 后台 | ✅ 选定：业务模型是行业标准（PMS/OMS/SMS/UMS），文档最全，数据模型同源 |
| YunaiV/ruoyi-vue-pro | 40.0k | Spring Boot + MyBatis-Plus | 商城模块深度耦合 yudao 框架（租户/权限），搬迁成本高 |
| linlinjava/litemall | 20.4k | Spring Boot + Vue + 小程序 | 轻量但功能少、维护慢 |
| newbee-ltd/newbee-mall | 11.7k | Spring Boot + Vue3 + Element Plus | 前端栈一致但功能浅（无多级分类/营销） |

采用的 mall 核心设计（而非照抄代码）：

1. **分类/品牌/SKU 三表独立**（对应 mall 的 `pms_product_category` / `pms_brand` / `pms_sku_stock`）。
2. **冗余名称列**：mall 的 `pms_product` 同时存 `product_category_id` + `product_category_name`。本项目沿用该模式——`product.category/brand` 字符串列保留为冗余展示列，由后端在保存商品、品牌改名时自动同步。**这是 AI 客服零改动的关键**：AI 工具的 `product_search(category=字符串)` 链路完全不变。

## 二、数据库变更（V9__mall_catalog_upgrade.sql）

| 表 | 说明 | 对标 |
| --- | --- | --- |
| `mall_category` | 层级分类：parent_id（0=一级）、level、nav_status（导航栏）、show_status、sort、icon | pms_product_category |
| `mall_brand` | 品牌：name、first_letter、logo、big_pic、brand_story、show_status、product_count | pms_brand |
| `mall_sku` | SKU：product_id、sku_code、sp_data（属性JSON）、price、stock、lock_stock、low_stock、pic、sale、status、version（乐观锁） | pms_sku_stock |
| `product` | 加列 `category_id` / `brand_id`（原字符串列保留为冗余） | pms_product 双字段模式 |
| `order_item` | 加列 `sku_id` / `sku_sp`（下单快照） | oms_order_item |
| `cart_item` | 加列 `sku_id`（0=无规格）；唯一键 `uk_user_product` → `uk_user_product_sku(user_id, product_id, sku_id)` | mall cart 设计 |

种子归一化：迁移自动把现有商品的 `category`/`brand` 字符串去重生成分类与品牌记录并回填 ID，存量数据零手工处理。

## 三、后端新增 / 变更

**新增**
- `entity/MallCategory`、`MallBrand`、`MallSku`（MallSku 带 @Version 乐观锁）
- `mapper/MallCategoryMapper`、`MallBrandMapper`、`MallSkuMapper`
- `product/CatalogService`：分类树（含在售商品计数）、品牌、SKU CRUD；SKU 变更后自动同步商品聚合（`stock=Σ SKU 库存`、`price=min SKU 价`，保证列表过滤 `stock>0` 与 AI 检索语义一致）
- `product/CatalogController`：买家端 `GET /api/v1/catalog/categories|brands|products/{id}/skus`
- `product/AdminCatalogController`：管理端 `/api/v1/admin/catalog/**`（分类/品牌/SKU 全套 CRUD）

**变更**
- `ProductService`：列表支持 `categoryId`/`brandId` 过滤（旧 `category` 字符串参数兼容）；商品保存按 ID 同步冗余名称列
- `OrderService`：下单/结算支持 `skuId`——有 SKU 走 SKU 价格与库存（乐观锁防超卖），同时扣商品级总库存；无 SKU（skuId 空/0）回落原路径；取消订单按快照回补 SKU 与商品库存
- `CartController`：加购带 `skuId`（商品有规格未指定时自动选最低价在售 SKU，老前端兜底）；购物车行展示 SKU 价格与属性；同商品不同规格为不同购物车行
- `MerchantController`：商品模板支持可选 `categoryId`/`brandId`

## 四、前端变更

- **商品详情**：SKU 规格选择器（按销售属性分组按钮组、选中组合定位 SKU、价格/库存联动、缺货阻断），无规格商品界面不变
- **商品列表**：品牌筛选下拉 + `categoryId`/`brandId` 路由参数过滤
- **首页**：分类宫格接真实分类树（`/catalog/categories`，导航栏分类优先），接口为空回落内置常量
- **购物车**：行内展示规格标签（如「颜色:黑色，容量:256G」）
- **管理后台**：商品管理改为三页签——商品（含规格管理弹窗：新增/停用/删除 SKU）、分类（树表格：加子分类/导航显隐/删除）、品牌（新增含品牌故事/显隐/删除）；新建商品表单改用分类级联选择 + 品牌下拉

## 五、兼容性验证

| 验证项 | 结果 |
| --- | --- |
| 后端全量测试 | **493 passed, 0 failed**（含订单生命周期、购物车并发事务、数字精确反序列化守卫） |
| 前端测试 + 类型检查 + 构建 | 152 passed / `tsc --noEmit` 通过 / `vite build` 通过 |
| AI 客服链路 | ai-service 目录**零改动**；`/internal/tools/product/search` 仍按 `product.category` 字符串检索，返回契约不变；AI 下单不传 skuId 时走原路径 |
| 存量数据 | V9 迁移自动归一化，无 SKU 商品的加购/下单/取消行为与改造前一致 |

## 六、三端自适应与响应式布局（2026-10-24 第二批）

统一断点体系：**手机 ≤768 ｜ 平板 769–1199 ｜ 桌面 ≥1200**。

| 模块 | 改造内容 |
| --- | --- |
| 全局设计系统（styles.css） | CSS 变量体系（品牌渐变 `#4f7cff→#8f6bff`、圆角、三级阴影）、Element 主色对齐、`.container` 自适应容器（1280px，三档内边距）、三端显隐工具类、滚动条美化、骨架屏动画；保留全部既有防溢出规则 |
| 买家端主布局（ClientLayout） | 品牌渐变 Logo + 圆角搜索框（桌面带搜索热词）+ 快捷入口 + 用户区；分类导航条接真实商城目录（`categoryId` 跳转、接口失败回落内置常量、双参数高亮）；三档顶栏高度 64/56/52px；手机端分类条横向滑动 |
| 底部导航（MobileTabbar） | 毛玻璃背景（backdrop-filter）、渐变文字激活态、按压微交互 |
| 商品卡片（ProductCard） | 卡片阴影体系、图片悬停微缩放、热卖标签（销量≥5000）、手机端收起卖点聚焦价格 |
| 首页（HomeView） | 分类宫格三端列数 10/5/4，楼层栅格 4/3/2，banner 高度三档（240/平板/140） |
| 商品列表（ProductListView） | 商品栅格固定列数 5/4/2（三端对齐），筛选栏窄屏两列换行 |
| 后台布局（Console/MerchantLayout） | 平板侧栏收窄 64px；手机侧栏隐藏 → 汉堡按钮 + `el-drawer` 抽屉菜单（选择菜单项自动关闭）；布局契约测试同步更新 |
| 其余买家页 | 收藏/历史/订单/详情/购物车/个人中心均已有 ≤768 适配（栅格降列、操作栏堆叠、480px 兜底），与统一断点兼容 |

## 七、营销中心（2026-10-24 第三批，对标 mall SMS）

对标 mall 的 `sms_coupon` / `sms_coupon_history` / `sms_seckill_*` 精简落地，接 V9 目录体系。

**数据库（V10__mall_promotion.sql）**

| 表 | 说明 |
| --- | --- |
| `mall_coupon` | 满减券模板：面额/门槛/发行量/已领量/领取时间窗/领券后有效天数 |
| `user_coupon` | 用户持券：UNUSED→USED→EXPIRED，`UNIQUE(coupon_id,user_id)` 每人限领一张，记录核销订单与过期时间 |
| `mall_seckill` | 商品秒杀：秒杀价/专属库存（乐观锁）/每人限购/时间窗 |
| `order_info` | 加 `discount_amount` / `coupon_user_id`（优惠与回补依据） |
| `order_item` | 加 `seckill_id`（秒杀明细快照） |

**核心规则**
- 下单时商品处于秒杀活动期 → 自动按秒杀价计算并扣秒杀专属库存（乐观锁防超卖），限购校验；
- 传入券 → 校验归属/状态/过期/门槛，订单落库同事务核销（状态条件更新防并发重复核销），优惠不超过订单额；
- **取消订单自动回补**：商品库存、SKU 库存、秒杀库存、优惠券（USED→UNUSED）；
- 领券余量原子扣减（`received_count < total_count` 条件更新）+ 唯一键仲裁重复领取。

**接口**
- 买家端 `/api/v1/promotions/**`：可领券列表、领券、我的券、结算可用券预览（按金额判门槛）、进行中秒杀
- 管理端 `/api/v1/admin/promotions/**`：券与秒杀 CRUD

**前端**
- 首页新增「⚡ 限时秒杀」楼层（倒计时、库存进度条、即将开始态）与「🎫 领券中心」楼层（三端栅格）
- 商品详情：秒杀价标签 + 划线原价 + 秒杀限购约束数量
- 下单弹窗（立即购买与购物车结算共用 `CouponPicker`）：按金额预览可用券、单选抵扣、显示应付与已优惠
- 个人中心「我的优惠券」列表（可用/已用/已过期）
- 管理后台「营销」页签：券管理（创建/上下架/删除，有领取不可删）与秒杀管理（创建/停启用/删除）

**验证**：后端 495 测试全过（AI 下单不传新参数走原路径，零回归）；前端 152 测试 + tsc + build 全过。

## 八、后续可继续对标的 mall 能力（未在本次范围）

- 营销中心（SMS）：优惠券、满减、秒杀、限时购
- 会员体系（UMS）：积分、成长值、等级
- 搜索增强：Elasticsearch 商品检索（当前为 MySQL LIKE + AI 混合检索）
- 物流对接：发货物流公司/单号联动、自动确认收货

## 九、深色模式 / 物流确认收货 / 搜索增强（2026-10-24 第四批，37fabfe）

**深色模式**：三态切换（浅色/深色/跟随系统），`html.dark` + Element dark css-vars + 自有
`--mall-surface/page-bg/surface-2` 变量体系；index.html 内联脚本防首屏闪烁；切换入口在
买家端顶栏/子头部与控制台、卖家中心头部；localStorage 持久化。32 个组件 scoped 样式
硬编码颜色批量替换为带 fallback 的变量（亮色渲染零变化）。

**物流与确认收货**（V11）：`order_info.delivery_company`；管理端发货可填物流公司；
买家端 SHIPPED 订单出现「确认收货」（本人校验 + 状态机 SHIPPED→DELIVERED）；
`OrderAutoConfirmJob` 每 30 分钟扫描发货满 7 天的订单自动完成（逐单推进，单笔失败跳过）。

**搜索增强**（V11）：`product` 加 ngram 全文索引（name/brand/selling_points），
买家端关键词搜索改走 `MATCH AGAINST` 自然语言模式并按相关度排序，索引异常自动降级
原 LIKE；AI 客服内部搜索链路零改动。选择 MySQL 全文而非 Elasticsearch：生产为
小内存 ARM 单机，ngram 方案零新增资源即可显著改善中文召回。

**验证**：后端 495 / 前端 152 测试 + tsc + build 全过；线上 V11 success=1、FULLTEXT
3 列、关键词「手表」相关度搜索命中、首页 200、暗色脚本已注入。

## 十、门户化视觉重构（2026-10-24 第五批，31b8769）

参考京东/mall 门户设计语言整体重构（此前为简洁风，用户反馈「不像商城」）：

- **三层电商头部**：顶部通栏（服务承诺+快捷链接）→ 主头部（大 Logo + 描边搜索框 +
  热词 + 带徽标购物车）→ 主题色导航条（「全部商品分类」hover 下拉 + 频道锚点）；
  手机端收敛为紧凑头部 + Tabbar。
- **首页**：第一屏三栏（分类竖菜单/大轮播/用户卡+公告）；秒杀专区模块化
  （红色倒计时面板 + 商品网格）；楼层标题品牌竖线；1200px 经典栅格。
- **列表页**：面包屑 + 左侧筛选侧栏（分类/品牌/价格）+ 排序条（综合/销量/价格升降，
  后端补 `sales_desc`）+ 移动端分类横滑 chips。
- **详情页（京东式）**：面包屑 + 浅红价格块（`--mall-price` #e4393c）+ 方形 SKU 按钮 +
  渐变 CTA + 介绍/参数 tabs 合并。
- 全站价格语义色统一电商红，暗色模式同步适配（价格块暗色变量）。

**验证**：后端 495 / 前端 152 + tsc + build 全过；线上容器 dist 确认新头部 chunk 已部署。
