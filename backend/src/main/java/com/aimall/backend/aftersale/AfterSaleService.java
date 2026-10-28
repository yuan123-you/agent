package com.aimall.backend.aftersale;

import com.aimall.backend.common.*;
import com.aimall.backend.entity.*;
import com.aimall.backend.mapper.*;
import com.aimall.backend.promotion.PromotionService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import static com.aimall.backend.aftersale.AfterSalePolicy.*;

@Service
@RequiredArgsConstructor
public class AfterSaleService {
    private final OrderInfoMapper orders;
    private final OrderItemMapper items;
    private final ProductMapper products;
    private final MallSkuMapper skus;
    private final AfterSaleMapper cases;
    private final MerchantMapper merchants;
    private final PromotionService promotions;
    private final ObjectMapper json;
    private final Clock clock;
    @Autowired private AfterSaleEvidenceStorage evidenceStorage;

    public record Apply(@JsonDeserialize(using=ExactNumberDeserializers.LongValue.class) Long orderId,
                        @JsonDeserialize(using=ExactNumberDeserializers.LongValue.class) Long orderItemId,
                        String serviceType, String issueCategory, String reason,
                        @JsonDeserialize(using=ExactNumberDeserializers.IntegerValue.class) Integer quantity,
                        BigDecimal refundAmount, List<String> evidence, String requestId) {}
    public record Command(String action, String reason, String recipient, String phone, String address,
                          String company, String trackingNo, Boolean restock) {}

    public OrderInfo owned(Long userId, Long orderId) {
        // Locking reads are current reads under MySQL REPEATABLE READ, not an earlier MVCC snapshot.
        OrderInfo order = org.springframework.transaction.support.TransactionSynchronizationManager.isActualTransactionActive()
                ? orders.selectForUpdate(orderId) : orders.selectById(orderId);
        if (order == null) throw new BizException(2002,"订单不存在");
        if (!Objects.equals(userId,order.getUserId())) throw new BizException(2003,"无权操作该订单");
        return order;
    }
    private List<OrderItem> orderItems(Long id) { return items.selectList(new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId,id).orderByAsc(OrderItem::getId)); }
    public List<AfterSale> orderCases(Long orderId) { var query=new LambdaQueryWrapper<AfterSale>().eq(AfterSale::getOrderId,orderId).orderByDesc(AfterSale::getId);
        if(org.springframework.transaction.support.TransactionSynchronizationManager.isActualTransactionActive())query.last("FOR UPDATE");
        return cases.selectList(query); }
    private BigDecimal money(AfterSale c) { return c.getApprovedRefundAmount() == null ? c.getRequestedRefundAmount() : c.getApprovedRefundAmount(); }
    private boolean consumes(AfterSale c) { return !RELEASED.contains(c.getStatus()) && !"ISSUE_REPORT".equals(c.getServiceType()); }
    private OrderItem requireItem(OrderInfo order, Long itemId) {
        if(itemId == null) throw invalid("请选择订单商品");
        OrderItem item=items.selectById(itemId);
        if(item==null || !Objects.equals(order.getId(),item.getOrderId())) throw invalid("订单商品无效");
        return item;
    }
    private BigDecimal cap(OrderInfo order, OrderItem item, int quantity, Long exclude) {
        var previous=orderCases(order.getId()).stream().filter(c -> Objects.equals(c.getOrderItemId(),item.getId()) && !Objects.equals(c.getId(),exclude) && consumes(c)).toList();
        int used=previous.stream().mapToInt(AfterSale::getQuantity).sum();
        BigDecimal reserved=previous.stream().filter(c -> !"EXCHANGE".equals(c.getServiceType())).map(this::money).reduce(BigDecimal.ZERO,BigDecimal::add);
        return refundCap(allocation(order.getTotalAmount(),orderItems(order.getId()),item.getId()),item.getQuantity(),used,quantity,reserved);
    }
    public BigDecimal quote(Long userId, Long orderId, Long itemId, String type, int quantity) {
        if(type==null)throw invalid("请选择售后类型");
        OrderInfo order=owned(userId,orderId); OrderItem item=requireItem(order,itemId);
        if (!services(order.getStatus()).contains(type) && !("ISSUE_REPORT".equals(type) && !services(order.getStatus()).isEmpty())) throw invalid("当前订单不支持该售后类型");
        if(orderCases(orderId).stream().anyMatch(c -> Objects.equals(c.getOrderItemId(),itemId) && !TERMINAL.contains(c.getStatus()))) throw invalid("该商品已有进行中的售后，请查看现有申请");
        BigDecimal maximum=cap(order,item,quantity,null);
        return Set.of("EXCHANGE","ISSUE_REPORT").contains(type) ? new BigDecimal("0.00") : maximum;
    }
    public List<Map<String,Object>> eligibility(Long userId, Long orderId) {
        OrderInfo order=owned(userId,orderId); List<AfterSale> all=orderCases(orderId);
        return orderItems(orderId).stream().map(item -> {
            Map<String,Object> e=new LinkedHashMap<>();
            var same=all.stream().filter(c -> Objects.equals(c.getOrderItemId(),item.getId())).toList();
            var active=same.stream().filter(c -> !TERMINAL.contains(c.getStatus())).findFirst();
            int used=same.stream().filter(this::consumes).mapToInt(AfterSale::getQuantity).sum();
            int remaining=Math.max(0,item.getQuantity()-used);
            e.put("orderItemId",item.getId());e.put("productName",item.getProductName());e.put("productImage",item.getProductImage());e.put("purchasedQuantity",item.getQuantity());
            e.put("availableQuantity",remaining);e.put("serviceTypes",active.isPresent() || remaining==0 ? List.of() : services(order.getStatus()));
            e.put("maxRefundAmount",remaining==0 || active.isPresent() ? BigDecimal.ZERO : cap(order,item,remaining,null));
            active.ifPresent(c -> e.put("activeAfterSaleId",c.getId()));
            e.put("unavailableReason",active.isPresent()?"已有进行中的售后":remaining==0?"可售后数量已用完":services(order.getStatus()).isEmpty()?"当前订单状态不可申请售后":"");
            return e;
        }).toList();
    }
    @Transactional
    public AfterSale apply(Long userId, Apply request, String actionId, Long conversationId) {
        if(request==null || request.orderId()==null || request.quantity()==null || request.quantity()<=0) throw invalid("申请参数不完整");
        String key=actionId==null ? "WEB-"+text(request.requestId(),64,"请求标识") : actionId;
        if(key.length()>64) throw invalid("请求标识过长");
        orders.lockOrder(request.orderId()); OrderInfo order=owned(userId,request.orderId());
        var existing=cases.selectOne(new LambdaQueryWrapper<AfterSale>().eq(AfterSale::getActionId,key));
        if(existing!=null) {
            if(!Objects.equals(existing.getUserId(),userId) || !Objects.equals(existing.getOrderItemId(),request.orderItemId()) || !Objects.equals(existing.getQuantity(),request.quantity()) || !Objects.equals(existing.getServiceType(),request.serviceType())) throw invalid("请求标识已用于其他申请");
            String fingerprint=storedRequestFingerprint(existing);
            if(fingerprint!=null) {
                if(!fingerprint.equals(requestFingerprint(request)))throw invalid("该请求已用于另一份申请，请先查看已提交的售后记录");
                return existing;
            }
            // Older rows do not record whether the original amount was defaulted. Do not guess.
            if(request.refundAmount()==null || !Objects.equals(existing.getOrderId(),request.orderId())
                    || !Objects.equals(existing.getIssueCategory(),request.issueCategory())
                    || !Objects.equals(existing.getReason(),request.reason()==null?null:request.reason().trim())
                    || existing.getRequestedRefundAmount().compareTo(request.refundAmount())!=0
                    || !read(existing.getEvidenceJson()).equals(request.evidence()==null?List.of():request.evidence())) throw invalid("历史申请或请求内容不一致，请查看已提交的售后记录");
            return existing;
        }
        String reason=text(request.reason(),500,"申请原因");
        if(!Set.of("PERSONAL","QUALITY","MERCHANT","PLATFORM").contains(request.issueCategory()==null?"":request.issueCategory())) throw invalid("问题分类无效");
        BigDecimal maximum=quote(userId,order.getId(),request.orderItemId(),request.serviceType(),request.quantity());
        BigDecimal amount=request.refundAmount()==null ? maximum : request.refundAmount();
        if(amount.scale()>2 || amount.signum()<0 || amount.compareTo(maximum)>0) throw invalid("退款金额超过按实付款分摊的可退金额");
        List<String> evidence=request.evidence()==null ? List.of() : request.evidence();
        if(evidence.size()>5) throw invalid("最多上传5张凭证");
        if(!evidence.isEmpty()) evidenceStorage.validate(userId,evidence);
        OrderItem item=requireItem(order,request.orderItemId()); Product product=products.selectById(item.getProductId());
        AfterSale c=new AfterSale(); c.setAfterSaleNo("AS"+UUID.randomUUID().toString().replace("-","").substring(0,28));
        c.setActionId(key);c.setOrderId(order.getId());c.setOrderItemId(item.getId());c.setUserId(userId);c.setMerchantId(product==null?null:product.getMerchantId());c.setConversationId(conversationId);
        c.setServiceType(request.serviceType());c.setIssueCategory(request.issueCategory());c.setReason(reason);c.setQuantity(request.quantity());c.setRequestedRefundAmount(amount);
        boolean platform=c.getMerchantId()==null || "PLATFORM".equals(c.getIssueCategory());
        c.setStatus(platform?"PENDING_PLATFORM":"PENDING_MERCHANT");c.setCurrentHandler(platform?"PLATFORM":"MERCHANT");
        c.setEvidenceJson(write(evidence));c.setHistoryJson("[]");c.setRefundMode("SIMULATED");c.setAppealed(false);c.setCreatedAt(now());c.setUpdatedAt(now());
        append(c,"APPLY","BUYER",userId,reason,requestFingerprint(request));cases.insert(c);return c;
    }
    public AfterSale authorized(Long userId,String role,Long id) {
        AfterSale c=cases.selectById(id);if(c==null)throw new BizException(2002,"售后单不存在");
        if("ADMIN".equals(role))return c;
        if("MERCHANT".equals(role) && Objects.equals(merchantId(userId),c.getMerchantId()))return c;
        if("CUSTOMER".equals(role) && Objects.equals(userId,c.getUserId()))return c;
        throw new BizException(2003,"无权查看该售后单");
    }
    private Long merchantId(Long userId) {
        Merchant m=merchants.selectOne(new LambdaQueryWrapper<Merchant>().eq(Merchant::getUserId,userId));
        if(m==null || !"ACTIVE".equals(m.getStatus()))throw new BizException(2003,"商家账号未开通或已停用");
        return m.getId();
    }
    private boolean operator(Long userId,String role,AfterSale c) {
        return ("ADMIN".equals(role) && "PLATFORM".equals(c.getCurrentHandler())) || ("MERCHANT".equals(role) && "MERCHANT".equals(c.getCurrentHandler()) && Objects.equals(merchantId(userId),c.getMerchantId()));
    }
    public List<String> actions(Long userId,String role,AfterSale c) {
        var result=new ArrayList<String>();
        if("CUSTOMER".equals(role) && Objects.equals(userId,c.getUserId())) {
            for(String command:List.of("CANCEL","RETURN","APPEAL","CONFIRM_EXCHANGE","CONVERT_REFUND")) {
                if("APPEAL".equals(command)&&Boolean.TRUE.equals(c.getAppealed()))continue;
                try {next(c.getServiceType(),c.getStatus(),command);result.add(command);}catch(BizException ignored){}
            }
        } else if(operator(userId,role,c)) {
            for(String command:List.of("APPROVE","REJECT","RECEIVE","REFUND","SHIP_EXCHANGE")) {
                try {next(c.getServiceType(),c.getStatus(),command);result.add(command);}catch(BizException ignored){}
            }
        }
        if("ADMIN".equals(role)&&!"PLATFORM".equals(c.getCurrentHandler())&&!TERMINAL.contains(c.getStatus()))result.add("TAKEOVER");
        return result;
    }
    @Transactional
    public AfterSale act(Long userId,String role,Long id,Command command) {
        AfterSale first=authorized(userId,role,id);orders.lockOrder(first.getOrderId());
        AfterSale c=org.springframework.transaction.support.TransactionSynchronizationManager.isActualTransactionActive() ? cases.selectForUpdate(id) : authorized(userId,role,id);
        if(c==null)throw new BizException(2002,"售后单不存在");
        String action=command==null?"":command.action();
        if("REFUND".equals(action)&&"REFUNDED".equals(c.getStatus())&&operator(userId,role,c))return c;
        if(!actions(userId,role,c).contains(action))throw new BizException(2003,"无权执行该操作，或售后状态已变化");
        String message=command.reason()==null?"":command.reason().trim();
        if(message.length()>500)throw invalid("说明不能超过500字");
        if("TAKEOVER".equals(action)) { c.setCurrentHandler("PLATFORM");if("PENDING_MERCHANT".equals(c.getStatus()))c.setStatus("PENDING_PLATFORM");message=text(message,500,"接管原因"); }
        else {
            String target=next(c.getServiceType(),c.getStatus(),action);
            if("REJECT".equals(action)) {c.setDecisionReason(text(message,500,"拒绝原因"));}
            if("APPEAL".equals(action)) {
                if(orderCases(c.getOrderId()).stream().anyMatch(other->!Objects.equals(other.getId(),c.getId()) && Objects.equals(other.getOrderItemId(),c.getOrderItemId()) && !TERMINAL.contains(other.getStatus())))throw invalid("该商品已有其他售后进行中，请勿重复申诉");
                OrderInfo order=owned(c.getUserId(),c.getOrderId());cap(order,requireItem(order,c.getOrderItemId()),c.getQuantity(),c.getId());
                message=text(message,500,"申诉说明");c.setAppealed(true);c.setCurrentHandler("PLATFORM");}
            if("APPROVE".equals(action)) {
                c.setDecisionReason(message);
                if(Set.of("RETURN_REFUND","EXCHANGE").contains(c.getServiceType())) {
                    c.setReturnRecipient(text(command.recipient(),80,"退货收件人"));c.setReturnPhone(text(command.phone(),40,"退货联系电话"));c.setReturnAddress(text(command.address(),500,"退货地址"));
                }
                if(!Set.of("EXCHANGE","ISSUE_REPORT").contains(c.getServiceType()))c.setApprovedRefundAmount(c.getRequestedRefundAmount().min(cap(owned(c.getUserId(),c.getOrderId()),requireItem(owned(c.getUserId(),c.getOrderId()),c.getOrderItemId()),c.getQuantity(),c.getId())));
            }
            if("CONVERT_REFUND".equals(action)) {
                OrderInfo order=owned(c.getUserId(),c.getOrderId());BigDecimal amount=cap(order,requireItem(order,c.getOrderItemId()),c.getQuantity(),c.getId());
                c.setServiceType("RETURN_REFUND");c.setRequestedRefundAmount(amount);c.setApprovedRefundAmount(amount);message="买家申请换货转退款，退件已验收，等待处理方执行退款";
            }
            if("RETURN".equals(action)) {c.setReturnCompany(text(command.company(),80,"退货物流公司"));c.setReturnTrackingNo(text(command.trackingNo(),100,"退货物流单号"));}
            if("RECEIVE".equals(action)&&Boolean.TRUE.equals(command.restock())) {adjustStock(c,c.getQuantity(),false);message=message+"（验收后回补可销售库存）";}
            if("SHIP_EXCHANGE".equals(action)) {
                c.setExchangeCompany(text(command.company(),80,"换货物流公司"));c.setExchangeTrackingNo(text(command.trackingNo(),100,"换货物流单号"));adjustStock(c,-c.getQuantity(),true);
            }
            if("REFUND".equals(action)) {
                OrderInfo order=owned(c.getUserId(),c.getOrderId());OrderItem item=requireItem(order,c.getOrderItemId());
                BigDecimal allowed=cap(order,item,c.getQuantity(),c.getId());
                if(money(c).compareTo(allowed)>0)throw invalid("退款金额超过剩余实付金额，请重新审核");
                c.setApprovedRefundAmount(money(c));c.setRefundReference("SIM-"+UUID.randomUUID());c.setRefundMode("SIMULATED");
                if("REFUND_ONLY".equals(c.getServiceType())&&"PAID".equals(order.getStatus())) {adjustStock(c,c.getQuantity(),false);c.setCancelledFulfillmentQuantity(c.getQuantity());}
                BigDecimal refunded=orderCases(order.getId()).stream().filter(v -> "REFUNDED".equals(v.getStatus())&&!Objects.equals(v.getId(),c.getId())).map(this::money).reduce(BigDecimal.ZERO,BigDecimal::add).add(money(c));
                var settled=new ArrayList<>(orderCases(order.getId()).stream().filter(v->"REFUNDED".equals(v.getStatus())&&!Objects.equals(v.getId(),c.getId())).toList());settled.add(c);
                boolean allUnitsRefunded=orderItems(order.getId()).stream().allMatch(line->settled.stream().filter(v->Objects.equals(v.getOrderItemId(),line.getId())).mapToInt(AfterSale::getQuantity).sum()>=line.getQuantity());
                if(allUnitsRefunded && !"REFUNDED".equals(order.getStatus())) {
                    OrderInfo update=new OrderInfo();update.setId(order.getId());update.setStatus("REFUNDED");if(orders.updateById(update)!=1)throw invalid("订单退款状态更新失败");
                    if(refunded.compareTo(order.getTotalAmount())>=0 && order.getCouponUserId()!=null)promotions.releaseCoupon(order.getCouponUserId());
                }
                message="模拟退款完成，不产生真实资金划转";
            }
            c.setStatus(target);
            c.setCompletedAt(TERMINAL.contains(target)?now():null);
        }
        c.setUpdatedAt(now());append(c,action,"ADMIN".equals(role)?"PLATFORM":"CUSTOMER".equals(role)?"BUYER":role,userId,message,null);
        if(cases.updateById(c)!=1)throw invalid("售后状态更新失败");return c;
    }
    private void adjustStock(AfterSale c,int delta,boolean requireOnSale) {
        OrderItem item=items.selectById(c.getOrderItemId());
        if(item==null)throw invalid("订单商品不存在，无法变更库存");
        if(delta>0&&item.getSeckillId()!=null) {promotions.restockSeckill(item.getSeckillId(),delta);return;}
        int changed=products.adjustAfterSaleStock(item.getProductId(),delta,requireOnSale);
        if(delta<0&&changed!=1)throw invalid("换货商品已下架或库存不足");
        if(item.getSkuId()!=null) {int skuChanged=skus.adjustAfterSaleStock(item.getSkuId(),delta,requireOnSale);if(delta<0&&skuChanged!=1)throw invalid("换货规格已下架或库存不足");}
    }
    public PageResult<Map<String,Object>> list(Long userId,String role,boolean manage,String status,Long orderId,long page,long size) {
        if(page<1||size<1||size>50)throw invalid("分页参数无效");
        var query=new LambdaQueryWrapper<AfterSale>().eq(status!=null&&!status.isBlank(),AfterSale::getStatus,status).eq(orderId!=null,AfterSale::getOrderId,orderId).orderByDesc(AfterSale::getId);
        if(!manage)query.eq(AfterSale::getUserId,userId);
        else if("MERCHANT".equals(role))query.eq(AfterSale::getMerchantId,merchantId(userId));
        else if(!"ADMIN".equals(role))throw new BizException(2003,"无权访问售后管理");
        return PageResult.of(cases.selectPage(new Page<>(page,size),query),c->view(userId,manage?role:"CUSTOMER",c));
    }
    public Map<String,Object> view(Long userId,String role,AfterSale c) {
        Map<String,Object> data=json.convertValue(c,new TypeReference<Map<String,Object>>(){});
        data.remove("historyJson");data.remove("evidenceJson");data.remove("actionId");
        data.put("history",read(c.getHistoryJson()));data.put("evidence",read(c.getEvidenceJson()));data.put("actions",actions(userId,role,c));
        OrderItem item=items.selectById(c.getOrderItemId());OrderInfo order=orders.selectById(c.getOrderId());
        if("EXCHANGE".equals(c.getServiceType()) && "WAITING_EXCHANGE".equals(c.getStatus()) && order!=null && item!=null)data.put("convertRefundAmount",cap(order,item,c.getQuantity(),c.getId()));
        data.put("productName",item==null?"历史订单商品":item.getProductName());data.put("productImage",item==null?null:item.getProductImage());data.put("orderNo",order==null?null:order.getOrderNo());return data;
    }
    public BigDecimal refundedAmount(Long orderId) { return orderCases(orderId).stream().filter(c->"REFUNDED".equals(c.getStatus())).map(this::money).reduce(BigDecimal.ZERO,BigDecimal::add); }
    public List<Map<String,Object>> forOrder(Long userId,Long orderId) {owned(userId,orderId);return orderCases(orderId).stream().map(c->view(userId,"CUSTOMER",c)).toList();}
    private String requestFingerprint(Apply request) {
        Map<String,Object> payload=new LinkedHashMap<>();
        payload.put("orderId",request.orderId());payload.put("orderItemId",request.orderItemId());
        payload.put("serviceType",request.serviceType());payload.put("issueCategory",request.issueCategory());
        payload.put("reason",request.reason()==null?null:request.reason().trim());payload.put("quantity",request.quantity());
        payload.put("amountMode",request.refundAmount()==null?"DEFAULT_MAXIMUM":"EXPLICIT");
        payload.put("amount",request.refundAmount()==null?"":request.refundAmount().stripTrailingZeros().toPlainString());
        payload.put("evidence",request.evidence()==null?List.of():request.evidence());
        try {return HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(write(payload).getBytes(java.nio.charset.StandardCharsets.UTF_8)));}
        catch(java.security.NoSuchAlgorithmException error){throw new IllegalStateException("SHA-256 unavailable",error);}
    }
    private String storedRequestFingerprint(AfterSale application) {
        for(Object event:read(application.getHistoryJson())) {
            if(event instanceof Map<?,?> entry && "APPLY".equals(entry.get("action")) && entry.get("requestFingerprint") instanceof String fingerprint)return fingerprint;
        }
        return null;
    }
    private void append(AfterSale c,String action,String actorRole,Long actorId,String message,String fingerprint) {
        List<Object> history=new ArrayList<>(read(c.getHistoryJson()));Map<String,Object> event=new LinkedHashMap<>();
        if(fingerprint!=null)event.put("requestFingerprint",fingerprint);
        event.put("action",action);event.put("status",c.getStatus());event.put("actorRole",actorRole);event.put("actorId",actorId);event.put("message",message);event.put("at",now().toString());history.add(event);c.setHistoryJson(write(history));
    }
    private List<Object> read(String source) {if(source==null||source.isBlank())return List.of();try{return json.readValue(source,new TypeReference<List<Object>>(){});}catch(Exception e){throw new BizException(5000,"售后记录数据异常");}}
    private String write(Object value) {try{return json.writeValueAsString(value);}catch(Exception e){throw new BizException(5000,"售后记录保存失败");}}
    private LocalDateTime now(){return LocalDateTime.now(clock);}
    private String text(String value,int max,String label){if(value==null||value.isBlank()||value.trim().length()>max)throw invalid("请填写有效的"+label+"（最多"+max+"字）");return value.trim();}
}
