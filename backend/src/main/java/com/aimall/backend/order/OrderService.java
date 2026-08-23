package com.aimall.backend.order;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Address;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.OrderItem;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.OrderItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 订单服务：下单（行锁防超卖）/支付/取消/查询/发货
 */
@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderInfoMapper orderInfoMapper;
    private final OrderItemMapper orderItemMapper;
    private final ProductMapper productMapper;
    private final OrderSseNotifier orderSseNotifier;
    private final AddressService addressService;

    private static final DateTimeFormatter NO_FMT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

    /** 下单（页面或 AI 工具统一入口）：事务 + 乐观锁防超卖 */
    @Transactional
    public OrderInfo create(Long userId, OrderDtos.CreateOrderRequest req, String source, Long conversationId) {
        DeliveryInfo delivery = resolveDelivery(userId, req.getAddressId(),
                req.getReceiverName(), req.getReceiverPhone(), req.getReceiverAddress());
        Product product = productMapper.selectById(req.getProductId());
        if (product == null || !"ON_SALE".equals(product.getStatus())) {
            throw new BizException(2005, "商品已下架");
        }
        deductStock(product, req.getQuantity());

        // 订单 + 明细（价格名称快照）
        BigDecimal subtotal = product.getPrice().multiply(BigDecimal.valueOf(req.getQuantity()));
        OrderInfo order = new OrderInfo();
        order.setOrderNo(genOrderNo());
        order.setUserId(userId);
        order.setTotalAmount(subtotal);
        order.setStatus("PENDING_PAYMENT");
        order.setReceiverName(delivery.name());
        order.setReceiverPhone(delivery.phone());
        order.setReceiverAddress(delivery.address());
        order.setSource(source);
        order.setConversationId(conversationId);
        orderInfoMapper.insert(order);

        OrderItem item = new OrderItem();
        item.setOrderId(order.getId());
        item.setProductId(product.getId());
        item.setProductName(product.getName());
        item.setProductImage(product.getImageUrl());
        item.setPrice(product.getPrice());
        item.setQuantity(req.getQuantity());
        item.setSubtotal(subtotal);
        orderItemMapper.insert(item);
        orderSseNotifier.publish(order);
        return order;
    }

    @Transactional
    public void pay(Long userId, Long orderId) {
        OrderInfo order = requireOwned(userId, orderId);
        if (!"PENDING_PAYMENT".equals(order.getStatus())) {
            throw new BizException(2004, "当前订单状态不可支付");
        }
        OrderInfo update = new OrderInfo();
        update.setId(order.getId());
        update.setStatus("PAID");
        update.setPaidAt(LocalDateTime.now());
        orderInfoMapper.updateById(update);
        order.setStatus("PAID");
        orderSseNotifier.publish(order);
    }

    @Transactional
    public void cancel(Long userId, Long orderId) {
        OrderInfo order = requireOwned(userId, orderId);
        if (!"PENDING_PAYMENT".equals(order.getStatus())) {
            throw new BizException(2004, "仅待支付订单可取消");
        }
        OrderInfo update = new OrderInfo();
        update.setId(order.getId());
        update.setStatus("CANCELLED");
        orderInfoMapper.updateById(update);
        // 回补库存
        for (OrderItem item : itemsOf(order.getId())) {
            Product product = productMapper.selectById(item.getProductId());
            if (product != null) {
                restock(product, item.getQuantity());
            }
        }
        order.setStatus("CANCELLED");
        orderSseNotifier.publish(order);
    }

    public Page<OrderInfo> myOrders(Long userId, String status, long page, long size) {
        return orderInfoMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<OrderInfo>()
                        .eq(OrderInfo::getUserId, userId)
                        .eq(status != null && !status.isBlank(), OrderInfo::getStatus, status)
                        .orderByDesc(OrderInfo::getId));
    }

    public OrderInfo requireOwned(Long userId, Long orderId) {
        OrderInfo order = orderInfoMapper.selectById(orderId);
        if (order == null) {
            throw new BizException(2002, "订单不存在");
        }
        if (!order.getUserId().equals(userId)) {
            throw new BizException(2003, "无权访问该订单");
        }
        return order;
    }

    public List<OrderItem> itemsOf(Long orderId) {
        return orderItemMapper.selectList(new LambdaQueryWrapper<OrderItem>()
                .eq(OrderItem::getOrderId, orderId));
    }

    // ---------- 管理端 ----------

    public Page<OrderInfo> adminList(String status, long page, long size) {
        return orderInfoMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<OrderInfo>()
                        .eq(status != null && !status.isBlank(), OrderInfo::getStatus, status)
                        .orderByDesc(OrderInfo::getId));
    }

    @Transactional
    public void ship(Long orderId, String logisticsNo) {
        OrderInfo order = orderInfoMapper.selectById(orderId);
        if (order == null) {
            throw new BizException(2002, "订单不存在");
        }
        if (!"PAID".equals(order.getStatus())) {
            throw new BizException(2004, "仅已支付订单可发货");
        }
        OrderInfo update = new OrderInfo();
        update.setId(order.getId());
        update.setStatus("SHIPPED");
        update.setLogisticsNo(logisticsNo);
        update.setShippedAt(LocalDateTime.now());
        orderInfoMapper.updateById(update);
        order.setStatus("SHIPPED");
        orderSseNotifier.publish(order);
    }

    @Transactional
    public void deliver(Long orderId) {
        OrderInfo order = orderInfoMapper.selectById(orderId);
        if (order == null) {
            throw new BizException(2002, "订单不存在");
        }
        if (!"SHIPPED".equals(order.getStatus())) {
            throw new BizException(2004, "仅已发货订单可标记送达");
        }
        OrderInfo update = new OrderInfo();
        update.setId(order.getId());
        update.setStatus("DELIVERED");
        update.setDeliveredAt(LocalDateTime.now());
        orderInfoMapper.updateById(update);
        order.setStatus("DELIVERED");
        orderSseNotifier.publish(order);
    }

    /** 购物车结算条目 */
    public record CheckoutItem(Long productId, Integer quantity) {
    }

    /** 购物车批量结算：多商品单订单（行锁逐一扣减，任一失败整体回滚） */
    @Transactional
    public OrderInfo checkout(Long userId, List<CheckoutItem> items, Long addressId,
                              String receiverName, String receiverPhone, String receiverAddress) {
        if (items == null || items.isEmpty()) {
            throw new BizException(2001, "结算商品不能为空");
        }
        DeliveryInfo delivery = resolveDelivery(userId, addressId, receiverName, receiverPhone, receiverAddress);
        BigDecimal total = BigDecimal.ZERO;
        List<OrderItem> pendingItems = new ArrayList<>();
        for (CheckoutItem ci : items) {
            if (ci.quantity() == null || ci.quantity() <= 0) {
                throw new BizException(2001, "商品数量无效");
            }
            Product product = productMapper.selectById(ci.productId());
            if (product == null || !"ON_SALE".equals(product.getStatus())) {
                throw new BizException(2005, "商品已下架：" + ci.productId());
            }
            deductStock(product, ci.quantity());
            BigDecimal subtotal = product.getPrice().multiply(BigDecimal.valueOf(ci.quantity()));
            total = total.add(subtotal);
            OrderItem item = new OrderItem();
            item.setProductId(product.getId());
            item.setProductName(product.getName());
            item.setProductImage(product.getImageUrl());
            item.setPrice(product.getPrice());
            item.setQuantity(ci.quantity());
            item.setSubtotal(subtotal);
            pendingItems.add(item);
        }

        OrderInfo order = new OrderInfo();
        order.setOrderNo(genOrderNo());
        order.setUserId(userId);
        order.setTotalAmount(total);
        order.setStatus("PENDING_PAYMENT");
        order.setReceiverName(delivery.name());
        order.setReceiverPhone(delivery.phone());
        order.setReceiverAddress(delivery.address());
        order.setSource("USER");
        orderInfoMapper.insert(order);
        for (OrderItem item : pendingItems) {
            item.setOrderId(order.getId());
            orderItemMapper.insert(item);
        }
        orderSseNotifier.publish(order);
        return order;
    }

    /**
     * 乐观锁扣减库存：基于读取时的 version 原子更新。
     * 并发冲突（updateById 影响 0 行）时重读重试，达上限即失败，杜绝超卖。
     */
    private void deductStock(Product p, int quantity) {
        updateStock(p, -quantity, "库存不足：" + p.getName());
    }

    private void restock(Product p, int quantity) {
        updateStock(p, quantity, "回补库存失败");
    }

    private void updateStock(Product product, int delta, String failMsg) {
        for (int attempt = 0; attempt < 5; attempt++) {
            Product current = attempt == 0 ? product : productMapper.selectById(product.getId());
            if (current == null) {
                throw new BizException(2005, "商品不存在");
            }
            int newStock = current.getStock() + delta;
            if (newStock < 0) {
                throw new BizException(2006, failMsg);
            }
            // @Version 乐观锁：影响行数为 0 表示版本冲突（他人并发修改）
            Product upd = new Product();
            upd.setId(current.getId());
            upd.setStock(newStock);
            upd.setVersion(current.getVersion());
            if (productMapper.updateById(upd) == 1) {
                return;
            }
        }
        throw new BizException(2006, "操作的人员过多，请重试");
    }


    private DeliveryInfo resolveDelivery(Long userId, Long addressId,
                                         String receiverName, String receiverPhone, String receiverAddress) {
        if (addressId != null) {
            return deliveryOf(addressService.forOrder(userId, addressId));
        }
        boolean hasName = receiverName != null && !receiverName.isBlank();
        boolean hasPhone = receiverPhone != null && !receiverPhone.isBlank();
        boolean hasAddress = receiverAddress != null && !receiverAddress.isBlank();
        if (!hasName && !hasPhone && !hasAddress) {
            return deliveryOf(addressService.defaultFor(userId));
        }
        if (!hasName || !hasPhone || !hasAddress) {
            throw new BizException(2001, "请完整填写收货信息");
        }
        String phone = receiverPhone.trim();
        if (!phone.matches("^1\\d{10}$")) {
            throw new BizException(2001, "请填写正确的手机号码");
        }
        return new DeliveryInfo(receiverName.trim(), phone, receiverAddress.trim());
    }

    private DeliveryInfo deliveryOf(Address address) {
        return new DeliveryInfo(address.getReceiverName(), address.getReceiverPhone(), address.getReceiverAddress());
    }

    private record DeliveryInfo(String name, String phone, String address) {
    }

    private String genOrderNo() {
        return "SO" + LocalDateTime.now().format(NO_FMT)
                + String.format("%03d", ThreadLocalRandom.current().nextInt(1000));
    }
}
