package com.aimall.backend.internal;

import com.aimall.backend.common.BizException;
import com.aimall.backend.address.AddressService;
import com.aimall.backend.entity.Address;
import com.aimall.backend.entity.AgentAction;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.AgentActionMapper;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.order.OrderDtos;
import com.aimall.backend.order.OrderService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class AgentOrderActionService {
    static final String ORDER_CREATE = "ORDER_CREATE";
    static final Duration ACTION_TTL = Duration.ofMinutes(10);

    private final AddressService addressService;
    private final AgentActionMapper actionMapper;
    private final ProductMapper productMapper;
    private final ConversationMapper conversationMapper;
    private final OrderInfoMapper orderInfoMapper;
    private final OrderService orderService;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public record PrepareRequest(Long userId, Long conversationId, Long productId, Integer quantity,
                                 String receiverName, String receiverPhone, String receiverAddress) {}
    public record ApprovalRequest(String receiverName, String receiverPhone, String receiverAddress) {}
    public record ActionStatusResult(String status, Long orderId, String orderNo) {}
    public record PrepareResult(String actionId, String productName, Integer quantity,
                                BigDecimal unitPrice, BigDecimal amount, String receiverName,
                                String receiverPhone, String receiverAddress, Instant expiresAt) {}

    @Transactional
    public PrepareResult prepare(PrepareRequest request) {
        validateCore(request);
        PrepareRequest prepared = withSavedDelivery(request);
        validateRequest(prepared);
        validateConversationOwner(prepared.userId(), prepared.conversationId());
        Product product = requireAvailableProduct(prepared.productId(), prepared.quantity());
        BigDecimal amount = product.getPrice().multiply(BigDecimal.valueOf(prepared.quantity()));
        Instant expiresAt = clock.instant().plus(ACTION_TTL);

        AgentAction action = new AgentAction();
        action.setActionId("act_" + UUID.randomUUID());
        action.setUserId(prepared.userId());
        action.setConversationId(prepared.conversationId());
        action.setType(ORDER_CREATE);
        action.setPayload(writePayload(prepared));
        action.setAmount(amount);
        action.setStatus("PENDING");
        action.setExpiresAt(expiresAt);
        actionMapper.insert(action);
        return new PrepareResult(action.getActionId(), product.getName(), prepared.quantity(),
                product.getPrice(), amount, prepared.receiverName(), prepared.receiverPhone(),
                prepared.receiverAddress(), expiresAt);
    }

    @Transactional
    public OrderInfo confirm(Long userId, String actionId) {
        return confirm(userId, actionId, null);
    }

    @Transactional
    public OrderInfo confirm(Long userId, String actionId, ApprovalRequest approval) {
        if (userId == null || actionId == null || actionId.isBlank()) {
            throw new BizException(2001, "缺少 userId 或 actionId");
        }
        AgentAction action = actionMapper.selectForUpdate(actionId);
        if (action == null || !ORDER_CREATE.equals(action.getType())) {
            throw new BizException(2010, "待确认操作不存在");
        }
        if (!action.getUserId().equals(userId)) {
            throw new BizException(2003, "无权确认该操作");
        }
        if ("CONFIRMED".equals(action.getStatus())) {
            OrderInfo existing = action.getOrderId() == null ? null : orderInfoMapper.selectById(action.getOrderId());
            if (existing != null && userId.equals(existing.getUserId())) return existing;
            throw new BizException(2012, "该操作已确认");
        }
        if (!"PENDING".equals(action.getStatus())) {
            throw new BizException(2012, "该操作当前不可确认");
        }
        if (!action.getExpiresAt().isAfter(clock.instant())) {
            throw new BizException(2011, "待确认操作已过期");
        }

        PrepareRequest request = readPayload(action.getPayload());
        if (approval != null) {
            request = new PrepareRequest(request.userId(), request.conversationId(), request.productId(), request.quantity(),
                    approval.receiverName(), approval.receiverPhone(), approval.receiverAddress());
        }
        validateRequest(request);
        if (!userId.equals(request.userId()) || !action.getConversationId().equals(request.conversationId())) {
            throw new BizException(2003, "操作快照归属校验失败");
        }
        validateConversationOwner(userId, request.conversationId());
        Product current = requireAvailableProduct(request.productId(), request.quantity());
        BigDecimal currentAmount = current.getPrice().multiply(BigDecimal.valueOf(request.quantity()));

        String idempotencyKey = idempotencyKey(request.conversationId(), request.productId());
        try {
            String existingId = redisTemplate.opsForValue().get(idempotencyKey);
            if (existingId != null) {
                OrderInfo existing = orderInfoMapper.selectById(Long.parseLong(existingId));
                if (existing != null && userId.equals(existing.getUserId())) {
                    if (actionMapper.markConfirmed(actionId, existing.getId(), existing.getTotalAmount()) != 1) {
                        throw new BizException(2012, "操作已被处理，请勿重复确认");
                    }
                    return existing;
                }
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception ignored) {
            // Redis 不可用或缓存失效时继续走数据库事务。
        }

        OrderDtos.CreateOrderRequest create = new OrderDtos.CreateOrderRequest();
        create.setProductId(request.productId());
        create.setQuantity(request.quantity());
        create.setReceiverName(request.receiverName());
        create.setReceiverPhone(request.receiverPhone());
        create.setReceiverAddress(request.receiverAddress());
        OrderInfo order = orderService.create(userId, create, "AI", request.conversationId());
        if (actionMapper.markConfirmed(actionId, order.getId(), order.getTotalAmount()) != 1) {
            throw new BizException(2012, "操作已被处理，请勿重复确认");
        }
        try {
            redisTemplate.opsForValue().set(idempotencyKey, String.valueOf(order.getId()), ACTION_TTL);
        } catch (Exception ignored) {
            // 数据库行锁和状态机是正确性保障；Redis 仅保留现有的快速幂等缓存能力。
        }
        return order;
    }

    @Transactional(readOnly = true)
    public ActionStatusResult status(Long userId, String actionId) {
        if (userId == null || actionId == null || actionId.isBlank()) {
            throw new BizException(2001, "缺少 userId 或 actionId");
        }
        AgentAction action = actionMapper.selectById(actionId);
        if (action == null || !ORDER_CREATE.equals(action.getType())) {
            throw new BizException(2010, "待确认操作不存在");
        }
        if (!action.getUserId().equals(userId)) {
            throw new BizException(2003, "无权查看该操作");
        }
        String status = "PENDING".equals(action.getStatus()) && !action.getExpiresAt().isAfter(clock.instant())
                ? "EXPIRED" : action.getStatus();
        OrderInfo order = action.getOrderId() == null ? null : orderInfoMapper.selectById(action.getOrderId());
        return new ActionStatusResult(status, order == null ? null : order.getId(),
                order == null ? null : order.getOrderNo());
    }

    @Transactional
    public void cancel(Long userId, String actionId) {
        if (userId == null || actionId == null || actionId.isBlank()) {
            throw new BizException(2001, "缺少 userId 或 actionId");
        }
        AgentAction action = actionMapper.selectForUpdate(actionId);
        if (action == null || !ORDER_CREATE.equals(action.getType())) {
            throw new BizException(2010, "待确认操作不存在");
        }
        if (!action.getUserId().equals(userId)) {
            throw new BizException(2003, "无权取消该操作");
        }
        if ("CANCELLED".equals(action.getStatus())) {
            return;
        }
        if (!"PENDING".equals(action.getStatus()) || actionMapper.markCancelled(actionId) != 1) {
            throw new BizException(2012, "该操作当前不可取消");
        }
    }
    @Scheduled(fixedDelayString = "${agent.action.expire-interval-ms:60000}")
    public void expirePendingActions() {
        actionMapper.expirePending(clock.instant());
    }

    private PrepareRequest withSavedDelivery(PrepareRequest request) {
        if (!blank(request.receiverName()) && !blank(request.receiverPhone()) && !blank(request.receiverAddress())) {
            return request;
        }
        Address saved = addressService.defaultFor(request.userId());
        return new PrepareRequest(request.userId(), request.conversationId(), request.productId(), request.quantity(),
                blank(request.receiverName()) ? saved.getReceiverName() : request.receiverName(),
                blank(request.receiverPhone()) ? saved.getReceiverPhone() : request.receiverPhone(),
                blank(request.receiverAddress()) ? saved.getReceiverAddress() : request.receiverAddress());
    }

    private void validateCore(PrepareRequest request) {
        if (request == null || request.userId() == null || request.conversationId() == null
                || request.productId() == null || request.quantity() == null || request.quantity() <= 0) {
            throw new BizException(2001, "缺少或无效的下单信息");
        }
    }

    private void validateRequest(PrepareRequest request) {
        if (request == null || request.userId() == null || request.conversationId() == null
                || request.productId() == null || request.quantity() == null || request.quantity() <= 0) {
            throw new BizException(2001, "缺少或无效的下单信息");
        }
        if (blank(request.receiverName()) || blank(request.receiverPhone()) || blank(request.receiverAddress())) {
            throw new BizException(2001, "缺少收货信息（姓名/电话/地址）");
        }
        if (request.receiverName().trim().length() > 50 || request.receiverAddress().trim().length() > 255) {
            throw new BizException(2001, "收货信息长度超出限制");
        }
        if (!request.receiverPhone().trim().matches("^1\\d{10}$")) {
            throw new BizException(2001, "请填写正确的手机号码");
        }
    }

    private void validateConversationOwner(Long userId, Long conversationId) {
        Conversation conversation = conversationMapper.selectById(conversationId);
        if (conversation == null || !userId.equals(conversation.getUserId())) {
            throw new BizException(2003, "无权操作该会话");
        }
    }

    private Product requireAvailableProduct(Long productId, int quantity) {
        Product product = productMapper.selectById(productId);
        if (product == null || !"ON_SALE".equals(product.getStatus())) {
            throw new BizException(2005, "商品已下架");
        }
        if (product.getStock() == null || product.getStock() < quantity) {
            throw new BizException(2006, "库存不足");
        }
        return product;
    }

    private String writePayload(PrepareRequest request) {
        try { return objectMapper.writeValueAsString(request); }
        catch (JsonProcessingException e) { throw new IllegalStateException("无法保存操作快照", e); }
    }

    private PrepareRequest readPayload(String payload) {
        try { return objectMapper.readValue(payload, PrepareRequest.class); }
        catch (JsonProcessingException e) { throw new BizException(2013, "操作快照损坏"); }
    }

    private String idempotencyKey(Long conversationId, Long productId) {
        return "ai:order:" + conversationId + ":" + productId;
    }
    private boolean blank(String value) { return value == null || value.isBlank(); }
}
