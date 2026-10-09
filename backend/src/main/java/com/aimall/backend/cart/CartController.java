package com.aimall.backend.cart;

import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.CartItem;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.CartItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.order.OrderService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.transaction.annotation.Transactional;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 购物车接口：/api/v1/cart（买家登录即可）
 */
@RestController
@RequestMapping("/api/v1/cart")
@RequiredArgsConstructor
public class CartController {

    private final CartItemMapper cartItemMapper;
    private final ProductMapper productMapper;
    private final OrderService orderService;

    @Data
    public static class AddBody {
        @NotNull
        @JsonDeserialize(using = ExactCartNumberDeserializers.LongValue.class)
        private Long productId;
        @NotNull
        @Min(1)
        @Max(99)
        @JsonDeserialize(using = ExactCartNumberDeserializers.IntegerValue.class)
        private Integer quantity;
    }

    @Data
    public static class CheckoutBody {
        private List<CheckoutItemBody> items;
        @JsonDeserialize(using = ExactCartNumberDeserializers.LongValue.class)
        private Long addressId;
        private String receiverName;
        private String receiverPhone;
        private String receiverAddress;
    }

    @Data
    public static class CheckoutItemBody {
        @JsonDeserialize(using = ExactCartNumberDeserializers.LongValue.class)
        private Long productId;
        @JsonDeserialize(using = ExactCartNumberDeserializers.IntegerValue.class)
        private Integer quantity;
    }

    /** Preserve omitted-vs-null fields without first decoding quantity through Map<Double>. */
    public static class UpdateBody {
        @JsonDeserialize(using = ExactCartNumberDeserializers.IntegerValue.class)
        private Integer quantity;
        private Object checked;
        private boolean quantityPresent;
        private boolean checkedPresent;

        public Integer getQuantity() { return quantity; }
        public void setQuantity(Integer quantity) {
            this.quantity = quantity;
            this.quantityPresent = true;
        }
        public Object getChecked() { return checked; }
        public void setChecked(Object checked) {
            this.checked = checked;
            this.checkedPresent = true;
        }
        private Map<String, Object> toMap() {
            Map<String, Object> values = new HashMap<>();
            if (quantityPresent) values.put("quantity", quantity);
            if (checkedPresent) values.put("checked", checked);
            return values;
        }
    }

    /** 加入购物车（已存在则累加数量） */
    @PostMapping("/items")
    public ApiResponse<Void> add(@AuthenticationPrincipal Long userId, @Valid @RequestBody AddBody body) {
        if (body == null || body.getProductId() == null || body.getProductId() <= 0
                || body.getQuantity() == null || body.getQuantity() < 1 || body.getQuantity() > 99) {
            throw new BizException(2001, "商品和数量不合法");
        }
        Product product = productMapper.selectById(body.getProductId());
        if (product == null || !"ON_SALE".equals(product.getStatus())) {
            throw new BizException(2005, "商品不存在或已下架");
        }
        // Each SQL statement is atomic. Do not compute replacements from a stale cart read.
        if (cartItemMapper.increment(userId, body.getProductId(), body.getQuantity()) == 1) {
            return ApiResponse.ok();
        }
        try {
            if (cartItemMapper.insertGuarded(userId, body.getProductId(), body.getQuantity()) == 1) {
                return ApiResponse.ok();
            }
        } catch (DuplicateKeyException competingInsert) {
            // The existing unique user/product key arbitrates simultaneous first additions.
            if (cartItemMapper.increment(userId, body.getProductId(), body.getQuantity()) == 1) {
                return ApiResponse.ok();
            }
        }
        throw new BizException(2006, "超出库存或商品状态已变化");
    }

    /** 购物车列表（含商品快照与合计） */
    @GetMapping
    public ApiResponse<Map<String, Object>> list(@AuthenticationPrincipal Long userId) {
        List<CartItem> items = cartItemMapper.selectList(new LambdaQueryWrapper<CartItem>()
                .eq(CartItem::getUserId, userId)
                .orderByDesc(CartItem::getId));
        List<Map<String, Object>> rows = new ArrayList<>();
        BigDecimal total = BigDecimal.ZERO;
        int checkedCount = 0;
        for (CartItem ci : items) {
            Product p = productMapper.selectById(ci.getProductId());
            if (p == null) {
                continue;
            }
            Map<String, Object> row = new HashMap<>();
            row.put("cartItemId", ci.getId());
            row.put("productId", p.getId());
            row.put("name", p.getName());
            row.put("imageUrl", p.getImageUrl());
            row.put("price", p.getPrice());
            row.put("quantity", ci.getQuantity());
            row.put("checked", ci.getChecked());
            row.put("stock", p.getStock());
            BigDecimal subtotal = p.getPrice().multiply(BigDecimal.valueOf(ci.getQuantity()));
            row.put("subtotal", subtotal);
            rows.add(row);
            if (ci.getChecked() == 1) {
                total = total.add(subtotal);
                checkedCount++;
            }
        }
        Map<String, Object> data = new HashMap<>();
        data.put("items", rows);
        data.put("totalAmount", total);
        data.put("checkedCount", checkedCount);
        return ApiResponse.ok(data);
    }

    /** 修改数量 / 勾选状态 */
    @PutMapping("/items/{id}")
    public ApiResponse<Void> updateHttp(@AuthenticationPrincipal Long userId, @PathVariable Long id,
                                        @RequestBody UpdateBody body) {
        return update(userId, id, body.toMap());
    }

    /** Compatibility entry for direct Java callers; HTTP quantities arrive already exact. */
    public ApiResponse<Void> update(Long userId, Long id, Map<String, Object> body) {
        requireOwned(userId, id);
        Integer checked = body.containsKey("checked") ? (Boolean.TRUE.equals(body.get("checked")) ? 1 : 0) : null;
        if (body.containsKey("quantity")) {
            int qty = requireQuantity(body.get("quantity"));
            if (cartItemMapper.setQuantity(id, userId, qty, checked) != 1) {
                throw new BizException(2006, "超出库存或购物车项状态已变化");
            }
        } else if (checked != null) {
            CartItem upd = new CartItem();
            upd.setChecked(checked);
            if (cartItemMapper.update(upd, new LambdaUpdateWrapper<CartItem>()
                    .eq(CartItem::getId, id).eq(CartItem::getUserId, userId)) != 1) {
                throw new BizException(2002, "购物车项不存在");
            }
        }
        return ApiResponse.ok();
    }

    private int requireQuantity(Object value) {
        if (!(value instanceof Number)) {
            throw new BizException(2001, "数量必须为正整数");
        }
        try {
            int quantity = new BigDecimal(value.toString()).intValueExact();
            if (quantity > 0) return quantity;
        } catch (ArithmeticException | NumberFormatException invalid) {
            // No decimal truncation or integer overflow.
        }
        throw new BizException(2001, "数量必须为正整数");
    }

    /** 批量勾选（ids 为空 = 全选/全不选，由 checked 决定） */
    @PutMapping("/check-all")
    public ApiResponse<Void> checkAll(@AuthenticationPrincipal Long userId, @RequestBody Map<String, Object> body) {
        boolean checked = Boolean.TRUE.equals(body.get("checked"));
        List<CartItem> items = cartItemMapper.selectList(new LambdaQueryWrapper<CartItem>()
                .eq(CartItem::getUserId, userId));
        for (CartItem item : items) {
            CartItem upd = new CartItem();
            upd.setId(item.getId());
            upd.setChecked(checked ? 1 : 0);
            cartItemMapper.updateById(upd);
        }
        return ApiResponse.ok();
    }

    @DeleteMapping("/items/{id}")
    public ApiResponse<Void> remove(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        requireOwned(userId, id);
        if (cartItemMapper.delete(new LambdaQueryWrapper<CartItem>()
                .eq(CartItem::getId, id).eq(CartItem::getUserId, userId)) != 1) {
            throw new BizException(2002, "购物车项不存在");
        }
        return ApiResponse.ok();
    }

    /** 购物车结算（勾选商品 → 多商品订单） */
    @Transactional
    @PostMapping("/checkout")
    public ApiResponse<Map<String, Object>> checkout(@AuthenticationPrincipal Long userId,
                                                     @RequestBody CheckoutBody body) {
        List<OrderService.CheckoutItem> items = new ArrayList<>();
        List<CartItem> snapshots;
        if (body.getItems() != null && !body.getItems().isEmpty()) {
            // 指定商品结算
            for (CheckoutItemBody b : body.getItems()) {
                if (b == null) {
                    throw new BizException(2001, "结算商品不能为空");
                }
                if (b.getProductId() == null || b.getProductId() <= 0 || b.getQuantity() == null || b.getQuantity() <= 0) {
                    throw new BizException(2001, "结算商品和数量不合法");
                }
                items.add(new OrderService.CheckoutItem(b.getProductId(), b.getQuantity()));
            }
            // Explicit buy-now remains valid without a cart row. Lock only existing matching rows.
            snapshots = cartItemMapper.selectList(new LambdaQueryWrapper<CartItem>()
                    .eq(CartItem::getUserId, userId)
                    .in(CartItem::getProductId, items.stream().map(OrderService.CheckoutItem::productId).toList())
                    .orderByAsc(CartItem::getProductId).last("FOR UPDATE"));
        } else {
            // 勾选商品结算
            List<CartItem> checked = cartItemMapper.selectList(new LambdaQueryWrapper<CartItem>()
                    .eq(CartItem::getUserId, userId)
                    .eq(CartItem::getChecked, 1)
                    .orderByAsc(CartItem::getProductId).last("FOR UPDATE"));
            snapshots = checked;
            if (checked.isEmpty()) {
                throw new BizException(2001, "请先勾选要结算的商品");
            }
            for (CartItem ci : checked) {
                items.add(new OrderService.CheckoutItem(ci.getProductId(), ci.getQuantity()));
            }
        }
        var order = orderService.checkout(userId, items, body.getAddressId(),
                body.getReceiverName(), body.getReceiverPhone(), body.getReceiverAddress());
        // Only the locked pre-order snapshot can be cleared. A persistence failure rolls back the order too.
        for (CartItem snapshot : snapshots) {
            int deleted = cartItemMapper.delete(new LambdaQueryWrapper<CartItem>()
                    .eq(CartItem::getId, snapshot.getId())
                    .eq(CartItem::getUserId, userId)
                    .eq(CartItem::getProductId, snapshot.getProductId())
                    .eq(CartItem::getQuantity, snapshot.getQuantity()));
            if (deleted != 1) {
                throw new BizException(2004, "购物车项已变化，请刷新后重试");
            }
        }
        Map<String, Object> data = new HashMap<>();
        data.put("orderId", order.getId());
        data.put("orderNo", order.getOrderNo());
        data.put("totalAmount", order.getTotalAmount());
        data.put("status", order.getStatus());
        return ApiResponse.ok(data);
    }

    private CartItem requireOwned(Long userId, Long id) {
        CartItem item = cartItemMapper.selectById(id);
        if (item == null || !item.getUserId().equals(userId)) {
            throw new BizException(2002, "购物车项不存在");
        }
        return item;
    }
}
