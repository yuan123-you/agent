package com.aimall.backend.internal;

import com.aimall.backend.common.BizException;
import com.aimall.backend.address.AddressService;
import com.aimall.backend.entity.Address;
import com.aimall.backend.entity.AfterSale;
import com.aimall.backend.entity.OrderItem;
import com.aimall.backend.entity.AgentAction;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.AgentActionMapper;
import com.aimall.backend.mapper.AfterSaleMapper;
import com.aimall.backend.mapper.OrderItemMapper;
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
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class AgentOrderActionService {
    public static final String ORDER_CREATE = "ORDER_CREATE";
    public static final String ORDER_CANCEL = "ORDER_CANCEL";
    public static final String AFTER_SALE_APPLY = "AFTER_SALE_APPLY";
    static final Duration ACTION_TTL = Duration.ofMinutes(10);

    private final AddressService addressService;
    private final AgentActionMapper actionMapper;
    private final ProductMapper productMapper;
    private final ConversationMapper conversationMapper;
    private final OrderInfoMapper orderInfoMapper;
    private final OrderItemMapper orderItemMapper;
    private final AfterSaleMapper afterSaleMapper;
    private final OrderService orderService;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    @org.springframework.beans.factory.annotation.Autowired
    private com.aimall.backend.aftersale.AfterSaleService afterSaleService;

    public record PrepareRequest(Long userId, Long conversationId, Long productId, Integer quantity,
                                 String receiverName, String receiverPhone, String receiverAddress) {}
    public record ApprovalRequest(String receiverName, String receiverPhone, String receiverAddress) {}
    public record CancelPrepareRequest(Long userId, Long conversationId, Long orderId, String reason) {}
    public record AfterSalePrepareRequest(Long userId, Long conversationId, Long orderId, Long orderItemId,
                                          String serviceType, String issueCategory, String reason, Integer quantity) {}
    public record BusinessPrepareResult(String type, String actionId, Long orderId, String orderNo,
                                        Long orderItemId, String productName, String serviceType,
                                        String issueCategory, String reason, Integer quantity,
                                        BigDecimal amount, Instant expiresAt) {}
    public record BusinessConfirmResult(String type, String status, Long orderId, String orderNo,
                                        String orderStatus, Long afterSaleId, String afterSaleNo) {}
    public record ActionStatusResult(String type, String status, Long orderId, String orderNo,
                                     Long afterSaleId, String afterSaleNo) {
        public ActionStatusResult(String status, Long orderId, String orderNo) {
            this(ORDER_CREATE, status, orderId, orderNo, null, null);
        }
    }
    public record PrepareResult(String actionId, String productName, Integer quantity,
                                BigDecimal unitPrice, BigDecimal amount, String receiverName,
                                String receiverPhone, String receiverAddress, Instant expiresAt) {}

    @Transactional
    public PrepareResult prepare(PrepareRequest request) {
        validateCore(request);
        PrepareRequest prepared = withSavedDelivery(request);
        validateRequest(prepared);
        validateConversationOwner(prepared.userId(), prepared.conversationId());
        Product product = requireAvailableProduct(prepared.productId());
        BigDecimal amount = orderService.quoteForAgent(prepared.userId(), prepared.productId(), prepared.quantity());
        if (amount == null || amount.signum() < 0) throw new BizException(2013, "报价快照无效，请重新发起确认");
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
                amount.divide(BigDecimal.valueOf(prepared.quantity()), 2, java.math.RoundingMode.HALF_UP), amount, prepared.receiverName(), prepared.receiverPhone(),
                prepared.receiverAddress(), expiresAt);
    }

    @Transactional
    public BusinessPrepareResult prepareCancel(CancelPrepareRequest request) {
        validateBusinessCore(request == null ? null : request.userId(), request == null ? null : request.conversationId());
        validateConversationOwner(request.userId(), request.conversationId());
        OrderInfo order = requireOwnedOrder(request.userId(), request.orderId());
        if (!"PENDING_PAYMENT".equals(order.getStatus())) {
            throw new BizException(2004, "仅待支付订单可取消");
        }
        String reason = requireReason(request.reason());
        AgentAction action = pendingBusinessAction(request.userId(), request.conversationId(), ORDER_CANCEL,
                request.orderId(), writePayload(request));
        actionMapper.insert(action);
        return new BusinessPrepareResult(ORDER_CANCEL, action.getActionId(), order.getId(), order.getOrderNo(),
                null, null, null, null, reason, null, BigDecimal.ZERO, action.getExpiresAt());
    }

    @Transactional
    public BusinessPrepareResult prepareAfterSale(AfterSalePrepareRequest request) {
        validateBusinessCore(request == null ? null : request.userId(), request == null ? null : request.conversationId());
        validateConversationOwner(request.userId(), request.conversationId());
        OrderInfo order = requireAfterSaleOrder(request.userId(), request.orderId());
        OrderItem item = requireOrderItem(order.getId(), request.orderItemId(), request.quantity());
        String serviceType = requireOneOf(request.serviceType(), Set.of("RETURN_REFUND", "EXCHANGE", "REFUND_ONLY", "ISSUE_REPORT"), "售后类型");
        String issueCategory = requireOneOf(request.issueCategory(), Set.of("PERSONAL", "QUALITY", "MERCHANT", "PLATFORM"), "问题分类");
        String reason = requireReason(request.reason());
        AfterSalePrepareRequest prepared = new AfterSalePrepareRequest(request.userId(), request.conversationId(),
                request.orderId(), request.orderItemId(), serviceType, issueCategory, reason, request.quantity());
        AgentAction action = pendingBusinessAction(request.userId(), request.conversationId(), AFTER_SALE_APPLY,
                request.orderId(), writePayload(prepared));
        actionMapper.insert(action);
        return new BusinessPrepareResult(AFTER_SALE_APPLY, action.getActionId(), order.getId(), order.getOrderNo(),
                item.getId(), item.getProductName(), serviceType, issueCategory, reason, request.quantity(),
                afterSaleService.quote(request.userId(), request.orderId(), request.orderItemId(), serviceType, request.quantity()), action.getExpiresAt());
    }

    @Transactional
    public BusinessConfirmResult confirmBusiness(Long userId, String actionId) {
        AgentAction action = requireOwnedLockedAction(userId, actionId);
        if ("CONFIRMED".equals(action.getStatus())) {
            OrderInfo order = requireOwnedOrder(userId, action.getTargetOrderId());
            if (ORDER_CANCEL.equals(action.getType())) {
                return new BusinessConfirmResult(ORDER_CANCEL, "CONFIRMED", order.getId(), order.getOrderNo(),
                        order.getStatus(), null, null);
            }
            if (AFTER_SALE_APPLY.equals(action.getType())) {
                AfterSale existing = afterSaleMapper.selectOne(
                        new LambdaQueryWrapper<AfterSale>().eq(AfterSale::getActionId, actionId));
                if (existing != null) return new BusinessConfirmResult(AFTER_SALE_APPLY, "CONFIRMED",
                        order.getId(), order.getOrderNo(), order.getStatus(), existing.getId(), existing.getAfterSaleNo());
            }
            throw new BizException(2012, "该操作已确认");
        }
        validatePendingAction(action);
        if (ORDER_CANCEL.equals(action.getType())) {
            CancelPrepareRequest request = readPayload(action.getPayload(), CancelPrepareRequest.class);
            validateBusinessSnapshot(action, userId, request.userId(), request.conversationId(), request.orderId());
            OrderInfo order = requireOwnedOrder(userId, request.orderId());
            if (!"PENDING_PAYMENT".equals(order.getStatus())) throw new BizException(2004, "订单当前不可取消");
            orderService.cancel(userId, order.getId());
            if (actionMapper.markBusinessConfirmed(actionId) != 1) throw new BizException(2012, "操作已被处理");
            return new BusinessConfirmResult(ORDER_CANCEL, "CONFIRMED", order.getId(), order.getOrderNo(),
                    "CANCELLED", null, null);
        }
        if (AFTER_SALE_APPLY.equals(action.getType())) {
            AfterSalePrepareRequest request = readPayload(action.getPayload(), AfterSalePrepareRequest.class);
            validateBusinessSnapshot(action, userId, request.userId(), request.conversationId(), request.orderId());
            OrderInfo order = requireAfterSaleOrder(userId, request.orderId());
            OrderItem item = requireOrderItem(order.getId(), request.orderItemId(), request.quantity());
            AfterSale afterSale = afterSaleService.apply(userId,
                    new com.aimall.backend.aftersale.AfterSaleService.Apply(order.getId(), item.getId(),
                            request.serviceType(), request.issueCategory(), request.reason(), request.quantity(),
                            null, java.util.List.of(), null), actionId, request.conversationId());
            if (actionMapper.markBusinessConfirmed(actionId) != 1) throw new BizException(2012, "操作已被处理");
            return new BusinessConfirmResult(AFTER_SALE_APPLY, "CONFIRMED", order.getId(), order.getOrderNo(),
                    order.getStatus(), afterSale.getId(), afterSale.getAfterSaleNo());
        }
        throw new BizException(2010, "待确认操作类型不支持");
    }

    public String typeOf(Long userId, String actionId) {
        AgentAction action = actionMapper.selectById(actionId);
        if (action == null) throw new BizException(2010, "待确认操作不存在");
        if (!action.getUserId().equals(userId)) throw new BizException(2003, "无权操作该请求");
        return action.getType();
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
        requireAvailableProduct(request.productId());
        BigDecimal currentAmount = orderService.quoteForAgent(userId, request.productId(), request.quantity());
        if (action.getAmount() == null || action.getAmount().signum() < 0) throw new BizException(2013, "报价快照无效，请重新发起确认");
        if (currentAmount == null || action.getAmount().compareTo(currentAmount) != 0) {
            throw new BizException(2015, "商品价格或优惠已变化，请重新核对报价并发起确认");
        }

        String idempotencyKey = idempotencyKey(actionId);
        try {
            String existingId = redisTemplate.opsForValue().get(idempotencyKey);
            if (existingId != null) {
                OrderInfo existing = orderInfoMapper.selectById(Long.parseLong(existingId));
                if (existing != null && userId.equals(existing.getUserId()) && "PENDING_PAYMENT".equals(existing.getStatus())
                        && existing.getTotalAmount() != null && existing.getTotalAmount().compareTo(action.getAmount()) == 0) {
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
        // A promotion may change between quoting and creation; the outer transaction must roll back.
        if (order == null || order.getTotalAmount() == null || order.getTotalAmount().compareTo(action.getAmount()) != 0) {
            throw new BizException(2015, "最终订单金额与已确认报价不一致，请重新核对");
        }
        if (actionMapper.markConfirmed(actionId, order.getId(), order.getTotalAmount()) != 1) {
            throw new BizException(2012, "操作已被处理，请勿重复确认");
        }
        cacheAfterCommit(idempotencyKey, order.getId());
        return order;
    }

    private void cacheAfterCommit(String key, Long orderId) {
        if (TransactionSynchronizationManager.isActualTransactionActive()
                && TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override public void afterCommit() { cacheOrder(key, orderId); }
            });
        } else {
            cacheOrder(key, orderId);
        }
    }

    private void cacheOrder(String key, Long orderId) {
        try {
            redisTemplate.opsForValue().set(key, String.valueOf(orderId), ACTION_TTL);
        } catch (Exception ignored) {
            // Database locks and action state remain authoritative if the post-commit cache write fails.
        }
    }
    @Transactional(readOnly = true)
    public ActionStatusResult status(Long userId, String actionId) {
        if (userId == null || actionId == null || actionId.isBlank()) {
            throw new BizException(2001, "缺少 userId 或 actionId");
        }
        AgentAction action = actionMapper.selectById(actionId);
        if (action == null) {
            throw new BizException(2010, "待确认操作不存在");
        }
        if (!action.getUserId().equals(userId)) {
            throw new BizException(2003, "无权查看该操作");
        }
        String status = "PENDING".equals(action.getStatus()) && !action.getExpiresAt().isAfter(clock.instant())
                ? "EXPIRED" : action.getStatus();
        Long linkedOrderId = action.getOrderId() != null ? action.getOrderId() : action.getTargetOrderId();
        OrderInfo order = linkedOrderId == null ? null : orderInfoMapper.selectById(linkedOrderId);
        AfterSale afterSale = AFTER_SALE_APPLY.equals(action.getType())
                ? afterSaleMapper.selectOne(new LambdaQueryWrapper<AfterSale>().eq(AfterSale::getActionId, actionId)) : null;
        return new ActionStatusResult(action.getType(), status, order == null ? null : order.getId(),
                order == null ? null : order.getOrderNo(), afterSale == null ? null : afterSale.getId(),
                afterSale == null ? null : afterSale.getAfterSaleNo());
    }

    @Transactional
    public void cancel(Long userId, String actionId) {
        if (userId == null || actionId == null || actionId.isBlank()) {
            throw new BizException(2001, "缺少 userId 或 actionId");
        }
        AgentAction action = actionMapper.selectForUpdate(actionId);
        if (action == null) {
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

    private AgentAction pendingBusinessAction(Long userId, Long conversationId, String type,
                                                    Long targetOrderId, String payload) {
        AgentAction action = new AgentAction(); action.setActionId("act_" + UUID.randomUUID());
        action.setUserId(userId); action.setConversationId(conversationId); action.setType(type);
        action.setPayload(payload); action.setAmount(BigDecimal.ZERO); action.setStatus("PENDING");
        action.setTargetOrderId(targetOrderId); action.setExpiresAt(clock.instant().plus(ACTION_TTL));
        return action;
    }

    private AgentAction requireOwnedLockedAction(Long userId, String actionId) {
        if (userId == null || actionId == null || actionId.isBlank()) throw new BizException(2001, "缺少操作信息");
        AgentAction action = actionMapper.selectForUpdate(actionId);
        if (action == null) throw new BizException(2010, "待确认操作不存在");
        if (!userId.equals(action.getUserId())) throw new BizException(2003, "无权确认该操作");
        return action;
    }

    private void validatePendingAction(AgentAction action) {
        if (!"PENDING".equals(action.getStatus())) throw new BizException(2012, "该操作当前不可确认");
        if (!action.getExpiresAt().isAfter(clock.instant())) throw new BizException(2011, "待确认操作已过期");
    }

    private void validateBusinessSnapshot(AgentAction action, Long authenticatedUserId, Long payloadUserId,
                                          Long conversationId, Long orderId) {
        if (!authenticatedUserId.equals(payloadUserId) || !action.getConversationId().equals(conversationId)
                || !action.getTargetOrderId().equals(orderId)) {
            throw new BizException(2003, "操作快照归属校验失败");
        }
        validateConversationOwner(authenticatedUserId, conversationId);
    }

    private OrderInfo requireOwnedOrder(Long userId, Long orderId) {
        OrderInfo order = orderInfoMapper.selectById(orderId);
        if (order == null || !userId.equals(order.getUserId())) throw new BizException(2003, "无权操作该订单");
        return order;
    }

    private OrderInfo requireAfterSaleOrder(Long userId, Long orderId) {
        OrderInfo order = requireOwnedOrder(userId, orderId);
        if (!Set.of("PAID", "SHIPPED", "DELIVERED").contains(order.getStatus()))
            throw new BizException(2004, "订单当前不可申请售后");
        return order;
    }

    private OrderItem requireOrderItem(Long orderId, Long itemId, Integer quantity) {
        if (itemId == null || quantity == null || quantity <= 0) throw new BizException(2001, "缺少订单商品或数量");
        OrderItem item = orderItemMapper.selectById(itemId);
        if (item == null || !orderId.equals(item.getOrderId()) || item.getQuantity() < quantity)
            throw new BizException(2001, "订单商品或申请数量无效");
        return item;
    }

    private void validateBusinessCore(Long userId, Long conversationId) {
        if (userId == null || conversationId == null) throw new BizException(2001, "缺少用户或会话信息");
    }

    private String requireReason(String reason) {
        if (blank(reason) || reason.trim().length() > 500) throw new BizException(2001, "请填写500字以内的原因");
        return reason.trim();
    }

    private String requireOneOf(String value, Set<String> allowed, String label) {
        String normalized = value == null ? "" : value.trim().toUpperCase();
        if (!allowed.contains(normalized)) throw new BizException(2001, label + "无效");
        return normalized;
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

    private Product requireAvailableProduct(Long productId) {
        Product product = productMapper.selectById(productId);
        if (product == null || !"ON_SALE".equals(product.getStatus())) {
            throw new BizException(2005, "商品已下架");
        }
        // Effective quote validation owns ordinary/SKU/seckill stock rules.
        if (product.getPrice() == null || product.getPrice().signum() < 0) {
            throw new BizException(2001, "商品价格无效");
        }
        return product;
    }

    private String writePayload(Object request) {
        try { return objectMapper.writeValueAsString(request); }
        catch (JsonProcessingException e) { throw new IllegalStateException("无法保存操作快照", e); }
    }

    private PrepareRequest readPayload(String payload) {
        return readPayload(payload, PrepareRequest.class);
    }

    private <T> T readPayload(String payload, Class<T> type) {
        try { return objectMapper.readValue(payload, type); }
        catch (JsonProcessingException e) { throw new BizException(2013, "操作快照损坏"); }
    }

    private String idempotencyKey(String actionId) {
        return "ai:order:action:" + actionId;
    }
    private boolean blank(String value) { return value == null || value.isBlank(); }
}
