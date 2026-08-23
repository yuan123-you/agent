package com.aimall.backend.internal;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.OrderItem;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.order.OrderService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.*;

/**
 * 内部工具回调接口：/internal/tools/**（仅 AI 服务，X-Internal-Token 鉴权）
 * <p>安全红线：userId 由后端发起对话时注入并随工具上下文传递；此处对会话类操作二次校验归属。</p>
 */
@RestController
@RequestMapping("/internal/tools")
@RequiredArgsConstructor
public class InternalToolController {

    private final ProductMapper productMapper;
    private final OrderInfoMapper orderInfoMapper;
    private final OrderService orderService;
    private final ConversationMapper conversationMapper;
    private final AgentOrderActionService agentOrderActionService;

    @Data
    public static class ProductSearchBody {
        private Long userId;
        private String keyword;
        private String category;
        private BigDecimal minPrice;
        private BigDecimal maxPrice;
        private Integer topK;
    }

    @Data
    public static class ProductDetailBody {
        private Long userId;
        private Long productId;
    }

    @Data
    public static class OrderQueryBody {
        private Long userId;
        private String status;
    }

    @Data
    public static class OrderCreateBody {
        private Long userId;
        private Long conversationId;
        private Long productId;
        private Integer quantity;
        private String receiverName;
        private String receiverPhone;
        private String receiverAddress;
    }

    @Data
    public static class EscalateBody {
        private Long userId;
        private Long conversationId;
        private String reason;
    }

    /** 中文类目名 → 类目编码（容错：LLM 可能传"手机"而非 PHONE） */
    private static final Map<String, String> CATEGORY_ALIAS = Map.ofEntries(
            Map.entry("手机", "PHONE"), Map.entry("手机数码", "PHONE"), Map.entry("数码", "PHONE"),
            Map.entry("电脑", "LAPTOP"), Map.entry("电脑办公", "LAPTOP"), Map.entry("笔记本", "LAPTOP"),
            Map.entry("家电", "APPLIANCE"), Map.entry("家用电器", "APPLIANCE"),
            Map.entry("服饰", "CLOTHING"), Map.entry("服饰内衣", "CLOTHING"), Map.entry("衣服", "CLOTHING"),
            Map.entry("美妆", "BEAUTY"), Map.entry("美妆个护", "BEAUTY"), Map.entry("个护", "BEAUTY"),
            Map.entry("食品", "FOOD"), Map.entry("食品生鲜", "FOOD"), Map.entry("生鲜", "FOOD"),
            Map.entry("母婴", "MATERNAL"), Map.entry("母婴玩具", "MATERNAL"), Map.entry("玩具", "MATERNAL"),
            Map.entry("运动", "SPORTS"), Map.entry("运动户外", "SPORTS"), Map.entry("户外", "SPORTS"),
            Map.entry("图书", "BOOK"), Map.entry("图书文娱", "BOOK"), Map.entry("书籍", "BOOK"),
            Map.entry("家居", "HOME"), Map.entry("家具家居", "HOME"), Map.entry("家具", "HOME"),
            Map.entry("珠宝", "JEWELRY"), Map.entry("珠宝饰品", "JEWELRY"), Map.entry("饰品", "JEWELRY"),
            Map.entry("箱包", "BAGS"), Map.entry("包", "BAGS"),
            Map.entry("鞋", "SHOES"), Map.entry("鞋靴", "SHOES"),
            Map.entry("宠物", "PET"), Map.entry("宠物生活", "PET"),
            Map.entry("医疗", "HEALTH"), Map.entry("保健", "HEALTH"), Map.entry("医疗保健", "HEALTH"),
            Map.entry("汽车", "CAR"), Map.entry("汽车用品", "CAR"), Map.entry("车品", "CAR"));

    private String normalizeCategory(String category) {
        if (category == null || category.isBlank()) {
            return null;
        }
        String trimmed = category.trim();
        return CATEGORY_ALIAS.getOrDefault(trimmed, trimmed.toUpperCase());
    }

    /** 商品检索（结构化条件 SQL 查询，返回规范化 link 供 AI 原样引用） */
    @PostMapping("/product/search")
    public ApiResponse<Map<String, Object>> productSearch(@RequestBody ProductSearchBody body) {
        int topK = body.getTopK() == null ? 5 : Math.min(body.getTopK(), 10);
        final String category = normalizeCategory(body.getCategory());
        // 复合关键词取最后一个词（容错：LLM 可能传"手机 拍照"导致 LIKE 不命中）
        String kw = body.getKeyword();
        if (kw != null && kw.contains(" ") && kw.split(" ").length == 2 && kw.length() <= 12) {
            kw = kw.split(" ")[kw.split(" ").length - 1];
        }
        final String keyword = kw;
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<Product>()
                .eq(Product::getStatus, "ON_SALE")
                .gt(Product::getStock, 0)
                .eq(category != null, Product::getCategory, category)
                .ge(body.getMinPrice() != null, Product::getPrice, body.getMinPrice())
                .le(body.getMaxPrice() != null, Product::getPrice, body.getMaxPrice())
                .and(keyword != null && !keyword.isBlank(), w -> w
                        .like(Product::getName, keyword)
                        .or().like(Product::getBrand, keyword)
                        .or().like(Product::getSellingPoints, keyword))
                .orderByAsc(Product::getPrice)
                .last("LIMIT " + topK);
        List<Product> products = productMapper.selectList(wrapper);
        List<Map<String, Object>> list = products.stream().map(p -> {
            Map<String, Object> vo = new HashMap<>();
            vo.put("productId", p.getId());
            vo.put("name", p.getName());
            vo.put("brand", p.getBrand());
            vo.put("category", p.getCategory());
            vo.put("price", p.getPrice());
            vo.put("stock", p.getStock());
            vo.put("sellingPoints", p.getSellingPoints());
            vo.put("link", "mall://product/" + p.getId());
            return vo;
        }).toList();
        return ApiResponse.ok(Map.of("products", list, "total", list.size()));
    }

    /** 商品语料同步（AI 服务商品向量化 job 拉取全量在售商品，含参数/介绍用于构建语料） */
    @PostMapping("/products/all")
    public ApiResponse<Map<String, Object>> productsAll() {
        List<Product> products = productMapper.selectList(new LambdaQueryWrapper<Product>()
                .eq(Product::getStatus, "ON_SALE")
                .gt(Product::getStock, 0)
                .orderByAsc(Product::getId));
        List<Map<String, Object>> list = products.stream().map(p -> {
            Map<String, Object> vo = new HashMap<>();
            vo.put("productId", p.getId());
            vo.put("name", p.getName());
            vo.put("brand", p.getBrand());
            vo.put("category", p.getCategory());
            vo.put("price", p.getPrice());
            vo.put("stock", p.getStock());
            vo.put("sales", p.getSales());
            vo.put("sellingPoints", p.getSellingPoints());
            vo.put("specs", p.getSpecs());
            vo.put("description", p.getDescription());
            return vo;
        }).toList();
        return ApiResponse.ok(Map.of("products", list, "total", list.size()));
    }

    /** 商品详情（比较类问题用） */
    @PostMapping("/product/detail")
    public ApiResponse<Map<String, Object>> productDetail(@RequestBody ProductDetailBody body) {
        Product p = productMapper.selectById(body.getProductId());
        if (p == null || !"ON_SALE".equals(p.getStatus())) {
            throw new BizException(2002, "商品不存在或已下架");
        }
        Map<String, Object> vo = new HashMap<>();
        vo.put("productId", p.getId());
        vo.put("name", p.getName());
        vo.put("brand", p.getBrand());
        vo.put("category", p.getCategory());
        vo.put("price", p.getPrice());
        vo.put("stock", p.getStock());
        vo.put("sellingPoints", p.getSellingPoints());
        vo.put("specs", p.getSpecs());
        String desc = p.getDescription() == null ? "" : p.getDescription();
        vo.put("description", desc.length() > 800 ? desc.substring(0, 800) : desc);
        vo.put("link", "mall://product/" + p.getId());
        return ApiResponse.ok(vo);
    }

    /** 订单查询（仅本人订单，脱敏 + link） */
    @PostMapping("/order/query")
    public ApiResponse<Map<String, Object>> orderQuery(@RequestBody OrderQueryBody body) {
        List<OrderInfo> orders = orderInfoMapper.selectList(new LambdaQueryWrapper<OrderInfo>()
                .eq(OrderInfo::getUserId, body.getUserId())
                .eq(body.getStatus() != null && !"ALL".equals(body.getStatus()),
                        OrderInfo::getStatus, body.getStatus())
                .orderByDesc(OrderInfo::getId)
                .last("LIMIT 5"));
        List<Map<String, Object>> list = orders.stream().map(o -> {
            Map<String, Object> vo = new HashMap<>();
            vo.put("orderId", o.getId());
            vo.put("orderNo", o.getOrderNo());
            vo.put("status", o.getStatus());
            vo.put("statusText", statusText(o.getStatus()));
            vo.put("logisticsNo", o.getLogisticsNo());
            vo.put("totalAmount", o.getTotalAmount());
            vo.put("createdAt", o.getCreatedAt());
            vo.put("items", orderService.itemsOf(o.getId()).stream().map(i -> Map.of(
                    "productId", i.getProductId(), "productName", i.getProductName(),
                    "quantity", i.getQuantity())).toList());
            vo.put("link", "mall://order/" + o.getId());
            return vo;
        }).toList();
        return ApiResponse.ok(Map.of("orders", list));
    }

    /** 准备 AI 下单：只保存待确认快照，绝不创建订单。 */
    @PostMapping("/order/prepare")
    public ApiResponse<AgentOrderActionService.PrepareResult> orderPrepare(@RequestBody OrderCreateBody body) {
        var request = new AgentOrderActionService.PrepareRequest(
                body.getUserId(), body.getConversationId(), body.getProductId(), body.getQuantity() == null ? 1 : body.getQuantity(),
                body.getReceiverName(), body.getReceiverPhone(), body.getReceiverAddress());
        return ApiResponse.ok(agentOrderActionService.prepare(request));
    }

    @Data
    public static class OrderConfirmBody {
        private Long userId;
        private String actionId;
    }

    /** 确认 AI 下单：唯一允许 AI 创建订单的入口。 */
    @PostMapping("/order/confirm")
    public ApiResponse<Map<String, Object>> orderConfirm(@RequestBody OrderConfirmBody body) {
        return ApiResponse.ok(orderVo(agentOrderActionService.confirm(body.getUserId(), body.getActionId())));
    }
    /** 转人工：会话置 PENDING_HUMAN */
    @PostMapping("/escalate")
    public ApiResponse<Map<String, Object>> escalate(@RequestBody EscalateBody body) {
        Conversation conv = conversationMapper.selectById(body.getConversationId());
        if (conv == null || !conv.getUserId().equals(body.getUserId())) {
            throw new BizException(2003, "无权操作该会话");
        }
        if ("ACTIVE".equals(conv.getStatus())) {
            Conversation upd = new Conversation();
            upd.setId(conv.getId());
            upd.setStatus("PENDING_HUMAN");
            conversationMapper.updateById(upd);
        }
        return ApiResponse.ok(Map.of("success", true));
    }

    private Map<String, Object> orderVo(OrderInfo order) {
        Map<String, Object> vo = new HashMap<>();
        vo.put("orderId", order.getId());
        vo.put("orderNo", order.getOrderNo());
        vo.put("totalAmount", order.getTotalAmount());
        vo.put("status", order.getStatus());
        vo.put("statusText", statusText(order.getStatus()));
        List<OrderItem> items = orderService.itemsOf(order.getId());
        vo.put("items", items.stream().map(i -> Map.of(
                "productId", i.getProductId(), "productName", i.getProductName(),
                "price", i.getPrice(), "quantity", i.getQuantity())).toList());
        vo.put("link", "mall://order/" + order.getId());
        return vo;
    }

    private String statusText(String status) {
        return switch (status) {
            case "PENDING_PAYMENT" -> "待支付";
            case "PAID" -> "已支付";
            case "SHIPPED" -> "已发货";
            case "DELIVERED" -> "已送达";
            case "CANCELLED" -> "已取消";
            default -> status;
        };
    }

    private boolean isBlank(String s) {
        return s == null || s.isBlank();
    }
}


