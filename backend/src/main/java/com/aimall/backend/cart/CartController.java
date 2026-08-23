package com.aimall.backend.cart;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.CartItem;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.CartItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.order.OrderService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
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
        private Long productId;
        @NotNull
        @Min(1)
        @Max(99)
        private Integer quantity;
    }

    @Data
    public static class CheckoutBody {
        private List<CheckoutItemBody> items;
        private Long addressId;
        private String receiverName;
        private String receiverPhone;
        private String receiverAddress;
    }

    @Data
    public static class CheckoutItemBody {
        private Long productId;
        private Integer quantity;
    }

    /** 加入购物车（已存在则累加数量） */
    @PostMapping("/items")
    public ApiResponse<Void> add(@AuthenticationPrincipal Long userId, @RequestBody AddBody body) {
        Product product = productMapper.selectById(body.getProductId());
        if (product == null || !"ON_SALE".equals(product.getStatus())) {
            throw new BizException(2005, "商品不存在或已下架");
        }
        CartItem exist = cartItemMapper.selectOne(new LambdaQueryWrapper<CartItem>()
                .eq(CartItem::getUserId, userId)
                .eq(CartItem::getProductId, body.getProductId()));
        if (exist != null) {
            int newQty = exist.getQuantity() + body.getQuantity();
            if (newQty > product.getStock()) {
                throw new BizException(2006, "超出库存，当前库存：" + product.getStock());
            }
            CartItem upd = new CartItem();
            upd.setId(exist.getId());
            upd.setQuantity(newQty);
            cartItemMapper.updateById(upd);
        } else {
            CartItem item = new CartItem();
            item.setUserId(userId);
            item.setProductId(body.getProductId());
            item.setQuantity(body.getQuantity());
            item.setChecked(1);
            cartItemMapper.insert(item);
        }
        return ApiResponse.ok();
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
    public ApiResponse<Void> update(@AuthenticationPrincipal Long userId, @PathVariable Long id,
                                    @RequestBody Map<String, Object> body) {
        CartItem item = requireOwned(userId, id);
        CartItem upd = new CartItem();
        upd.setId(item.getId());
        if (body.containsKey("quantity")) {
            int qty = ((Number) body.get("quantity")).intValue();
            Product p = productMapper.selectById(item.getProductId());
            if (p != null && qty > p.getStock()) {
                throw new BizException(2006, "超出库存");
            }
            upd.setQuantity(Math.max(1, qty));
        }
        if (body.containsKey("checked")) {
            upd.setChecked(Boolean.TRUE.equals(body.get("checked")) ? 1 : 0);
        }
        cartItemMapper.updateById(upd);
        return ApiResponse.ok();
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
        cartItemMapper.deleteById(id);
        return ApiResponse.ok();
    }

    /** 购物车结算（勾选商品 → 多商品订单） */
    @PostMapping("/checkout")
    public ApiResponse<Map<String, Object>> checkout(@AuthenticationPrincipal Long userId,
                                                     @RequestBody CheckoutBody body) {
        List<OrderService.CheckoutItem> items = new ArrayList<>();
        if (body.getItems() != null && !body.getItems().isEmpty()) {
            // 指定商品结算
            for (CheckoutItemBody b : body.getItems()) {
                items.add(new OrderService.CheckoutItem(b.getProductId(), b.getQuantity()));
            }
        } else {
            // 勾选商品结算
            List<CartItem> checked = cartItemMapper.selectList(new LambdaQueryWrapper<CartItem>()
                    .eq(CartItem::getUserId, userId)
                    .eq(CartItem::getChecked, 1));
            if (checked.isEmpty()) {
                throw new BizException(2001, "请先勾选要结算的商品");
            }
            for (CartItem ci : checked) {
                items.add(new OrderService.CheckoutItem(ci.getProductId(), ci.getQuantity()));
            }
        }
        var order = orderService.checkout(userId, items, body.getAddressId(),
                body.getReceiverName(), body.getReceiverPhone(), body.getReceiverAddress());
        // 结算后清除对应购物车项
        for (OrderService.CheckoutItem ci : items) {
            cartItemMapper.delete(new LambdaQueryWrapper<CartItem>()
                    .eq(CartItem::getUserId, userId)
                    .eq(CartItem::getProductId, ci.productId()));
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
