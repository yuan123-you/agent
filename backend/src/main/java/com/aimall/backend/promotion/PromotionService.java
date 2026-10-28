package com.aimall.backend.promotion;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.MallCoupon;
import com.aimall.backend.entity.MallSeckill;
import com.aimall.backend.entity.Product;
import com.aimall.backend.entity.UserCoupon;
import com.aimall.backend.mapper.MallCouponMapper;
import com.aimall.backend.mapper.MallSeckillMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.mapper.UserCouponMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 营销服务：优惠券（对标 mall sms_coupon）+ 商品秒杀（对标 mall sms_seckill）。
 *
 * 下单集成约定：
 *  - 秒杀：活动期内自动生效，价格取秒杀价，扣秒杀专属库存（乐观锁）；
 *  - 券：传入 couponUserId 时校验归属/状态/门槛，订单落库后核销，取消时回退；
 *  - AI 客服下单不传新参数，走原路径，行为与改造前完全一致。
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class PromotionService {

    private final MallCouponMapper couponMapper;
    private final UserCouponMapper userCouponMapper;
    private final MallSeckillMapper seckillMapper;
    private final ProductMapper productMapper;

    // ==================== 买家端 ====================

    /** 可领券列表：启用中、领取窗内、有余量、且当前用户未领过 */
    public List<Map<String, Object>> receivableCoupons(Long userId) {
        LocalDateTime now = LocalDateTime.now();
        List<MallCoupon> coupons = couponMapper.selectList(new LambdaQueryWrapper<MallCoupon>()
                .eq(MallCoupon::getStatus, "ENABLE")
                .and(w -> w.isNull(MallCoupon::getStartTime).or().le(MallCoupon::getStartTime, now))
                .and(w -> w.isNull(MallCoupon::getEndTime).or().ge(MallCoupon::getEndTime, now))
                .apply("received_count < total_count")
                .orderByDesc(MallCoupon::getId));
        Set<Long> received = userId == null ? Set.of() : userCouponMapper.selectList(
                        new LambdaQueryWrapper<UserCoupon>().eq(UserCoupon::getUserId, userId))
                .stream().map(UserCoupon::getCouponId).collect(Collectors.toSet());
        List<Map<String, Object>> rows = new ArrayList<>();
        for (MallCoupon c : coupons) {
            if (received.contains(c.getId())) {
                continue;
            }
            rows.add(couponView(c, false));
        }
        return rows;
    }

    /** 我的优惠券（联模板展示） */
    public List<Map<String, Object>> myCoupons(Long userId) {
        List<UserCoupon> mine = userCouponMapper.selectList(new LambdaQueryWrapper<UserCoupon>()
                .eq(UserCoupon::getUserId, userId)
                .orderByDesc(UserCoupon::getId));
        if (mine.isEmpty()) {
            return List.of();
        }
        Map<Long, MallCoupon> templates = couponMapper.selectBatchIds(
                        mine.stream().map(UserCoupon::getCouponId).distinct().toList())
                .stream().collect(Collectors.toMap(MallCoupon::getId, c -> c));
        List<Map<String, Object>> rows = new ArrayList<>();
        for (UserCoupon uc : mine) {
            MallCoupon c = templates.get(uc.getCouponId());
            Map<String, Object> row = new HashMap<>();
            row.put("userCouponId", uc.getId());
            row.put("couponId", uc.getCouponId());
            row.put("status", resolveStatus(uc));
            row.put("receivedAt", uc.getReceivedAt());
            row.put("expireAt", uc.getExpireAt());
            row.put("usedOrderId", uc.getUsedOrderId());
            if (c != null) {
                row.put("name", c.getName());
                row.put("discountValue", c.getDiscountValue());
                row.put("minAmount", c.getMinAmount());
            }
            rows.add(row);
        }
        return rows;
    }

    /** 领券：余量原子扣减 + 唯一键仲裁每人一张 */
    @Transactional
    public Long receive(Long userId, Long couponId) {
        MallCoupon coupon = couponMapper.selectById(couponId);
        if (coupon == null || !"ENABLE".equals(coupon.getStatus())) {
            throw new BizException(2201, "优惠券不存在或已下架");
        }
        LocalDateTime now = LocalDateTime.now();
        if (coupon.getStartTime() != null && now.isBefore(coupon.getStartTime())) {
            throw new BizException(2202, "优惠券尚未开始领取");
        }
        if (coupon.getEndTime() != null && now.isAfter(coupon.getEndTime())) {
            throw new BizException(2203, "优惠券领取已结束");
        }
        // 余量原子扣减：只有 received_count < total_count 的行能更新成功
        int updated = couponMapper.update(null,
                new com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper<MallCoupon>()
                        .eq(MallCoupon::getId, couponId)
                        .eq(MallCoupon::getStatus, "ENABLE")
                        .apply("(start_time IS NULL OR start_time <= CURRENT_TIMESTAMP)")
                        .apply("(end_time IS NULL OR end_time >= CURRENT_TIMESTAMP)")
                        .apply("received_count < total_count")
                        .setSql("received_count = received_count + 1"));
        if (updated != 1) {
            throw new BizException(2204, "优惠券已领完或领取状态已变化");
        }
        int validDays = coupon.getValidDays() == null ? 7 : coupon.getValidDays();
        UserCoupon uc = new UserCoupon();
        uc.setCouponId(couponId);
        uc.setUserId(userId);
        uc.setStatus("UNUSED");
        uc.setReceivedAt(now);
        uc.setExpireAt(now.plusDays(validDays));
        try {
            userCouponMapper.insert(uc);
        } catch (DuplicateKeyException already) {
            // 唯一键仲裁：每人每券一张；回滚本事务让余量扣减一并撤销
            throw new BizException(2205, "已经领取过该优惠券");
        }
        return uc.getId();
    }

    /** 进行中的秒杀（含即将开始），带商品快照 */
    public List<Map<String, Object>> activeSeckills() {
        LocalDateTime now = LocalDateTime.now();
        List<MallSeckill> list = seckillMapper.selectList(new LambdaQueryWrapper<MallSeckill>()
                .eq(MallSeckill::getStatus, "ENABLE")
                .gt(MallSeckill::getEndTime, now)
                .orderByAsc(MallSeckill::getStartTime)
                .orderByDesc(MallSeckill::getId));
        if (list.isEmpty()) {
            return List.of();
        }
        Map<Long, Product> products = productMapper.selectBatchIds(
                        list.stream().map(MallSeckill::getProductId).distinct().toList())
                .stream().collect(Collectors.toMap(Product::getId, p -> p));
        List<Map<String, Object>> rows = new ArrayList<>();
        for (MallSeckill s : list) {
            Product p = products.get(s.getProductId());
            if (p == null || !"ON_SALE".equals(p.getStatus())) {
                continue;
            }
            Map<String, Object> row = new HashMap<>();
            row.put("seckillId", s.getId());
            row.put("productId", p.getId());
            row.put("name", p.getName());
            row.put("imageUrl", p.getImageUrl());
            row.put("originalPrice", p.getPrice());
            row.put("seckillPrice", s.getSeckillPrice());
            row.put("seckillStock", s.getSeckillStock());
            row.put("seckillLimit", s.getSeckillLimit());
            row.put("startTime", s.getStartTime());
            row.put("endTime", s.getEndTime());
            row.put("started", !now.isBefore(s.getStartTime()));
            rows.add(row);
        }
        return rows;
    }

    // ==================== 下单集成 ====================

    /** 解析商品当前生效的秒杀活动；无活动返回 null */
    public MallSeckill resolveSeckill(Long productId) {
        LocalDateTime now = LocalDateTime.now();
        return seckillMapper.selectOne(new LambdaQueryWrapper<MallSeckill>()
                .eq(MallSeckill::getProductId, productId)
                .eq(MallSeckill::getStatus, "ENABLE")
                .le(MallSeckill::getStartTime, now)
                .ge(MallSeckill::getEndTime, now)
                .orderByDesc(MallSeckill::getId)
                .last("LIMIT 1"));
    }

    /** 秒杀下单校验：库存与限购 */
    public void validateSeckill(MallSeckill seckill, int quantity) {
        if (seckill.getSeckillStock() < quantity) {
            throw new BizException(2206, "秒杀库存不足");
        }
        int limit = seckill.getSeckillLimit() == null ? 1 : seckill.getSeckillLimit();
        if (quantity > limit) {
            throw new BizException(2207, "秒杀商品每人限购" + limit + "件");
        }
    }

    /** Pending orders reserve buyer quota. Only unpaid cancellation releases it; paid/refunded purchases
     * retain quota conservatively. Call inside the order transaction, before campaign stock changes.
     * requestedQuantity includes earlier lines for this campaign in the same checkout.
     */
    public void validateBuyerSeckill(Long userId, MallSeckill campaign, long requestedQuantity) {
        if (seckillMapper.lockBuyer(userId) == null) throw new BizException(2003, "买家账号不存在");
        checkBuyerQuota(userId, campaign, requestedQuantity, true);
    }

    /** Proposal validation only: no locks, reservations, or writes. Creation rechecks under the buyer lock. */
    public void validateBuyerSeckillQuote(Long userId, MallSeckill campaign, int quantity) {
        checkBuyerQuota(userId, campaign, quantity, false);
    }

    private void checkBuyerQuota(Long userId, MallSeckill campaign, long quantity, boolean locking) {
        long purchased = seckillMapper.entitlementQuantities(userId, campaign.getId(), locking)
                .stream().mapToLong(Integer::longValue).sum();
        int limit = campaign.getSeckillLimit() == null ? 1 : campaign.getSeckillLimit();
        if (quantity <= 0 || purchased + quantity > limit) {
            throw new BizException(2207, "秒杀商品每人累计限购" + limit + "件（待支付占用名额，已支付及退款订单不退名额）");
        }
    }

    /** 秒杀乐观锁扣减库存（失败抛错回滚订单事务） */
    public void deductSeckillStock(MallSeckill seckill, int quantity) {
        for (int attempt = 0; attempt < 5; attempt++) {
            MallSeckill current = attempt == 0 ? seckill : seckillMapper.selectById(seckill.getId());
            if (current == null) {
                throw new BizException(2206, "秒杀活动不存在");
            }
            if (current.getSeckillStock() < quantity) {
                throw new BizException(2206, "秒杀库存不足");
            }
            MallSeckill upd = new MallSeckill();
            upd.setId(current.getId());
            upd.setSeckillStock(current.getSeckillStock() - quantity);
            upd.setVersion(current.getVersion());
            if (seckillMapper.updateById(upd) == 1) {
                return;
            }
        }
        throw new BizException(2206, "秒杀活动火爆，请重试");
    }

    /** 秒杀库存回补（取消订单） */
    public void restockSeckill(Long seckillId, int quantity) {
        if (seckillId == null || quantity <= 0) {
            return;
        }
        for (int attempt = 0; attempt < 5; attempt++) {
            MallSeckill current = seckillMapper.selectById(seckillId);
            if (current == null) {
                return; // 活动已被删除，无需回补
            }
            MallSeckill upd = new MallSeckill();
            upd.setId(current.getId());
            upd.setSeckillStock(current.getSeckillStock() + quantity);
            upd.setVersion(current.getVersion());
            if (seckillMapper.updateById(upd) == 1) {
                return;
            }
        }
        throw new BizException(2206, "秒杀库存回补失败，请重试");
    }

    /** 券优惠金额校验（不核销）：返回优惠额 */
    public BigDecimal couponDiscount(Long userId, Long couponUserId, BigDecimal subtotal) {
        UserCoupon uc = requireUsableCoupon(userId, couponUserId);
        MallCoupon coupon = couponMapper.selectById(uc.getCouponId());
        if (coupon == null) {
            throw new BizException(2201, "优惠券不存在");
        }
        BigDecimal threshold = coupon.getMinAmount() == null ? BigDecimal.ZERO : coupon.getMinAmount();
        if (subtotal.compareTo(threshold) < 0) {
            throw new BizException(2208, "订单金额未达到优惠券使用门槛");
        }
        BigDecimal discount = coupon.getDiscountValue();
        return discount.min(subtotal); // 优惠不超过订单额
    }

    /** 核销券（订单创建成功同事务调用） */
    public void markCouponUsed(Long userId, Long couponUserId, Long orderId) {
        UserCoupon uc = requireUsableCoupon(userId, couponUserId);
        UserCoupon upd = new UserCoupon();
        upd.setId(uc.getId());
        upd.setStatus("USED");
        upd.setUsedOrderId(orderId);
        upd.setUsedAt(LocalDateTime.now());
        // 带状态条件更新，避免并发下重复核销
        int updated = userCouponMapper.update(upd,
                new com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper<UserCoupon>()
                        .eq(UserCoupon::getId, uc.getId())
                        .eq(UserCoupon::getStatus, "UNUSED"));
        if (updated != 1) {
            throw new BizException(2209, "优惠券已被使用，请刷新后重试");
        }
    }

    /** 取消订单回退券 */
    public void releaseCoupon(Long couponUserId) {
        if (couponUserId == null) {
            return;
        }
        UserCoupon uc = userCouponMapper.selectById(couponUserId);
        if (uc == null || !"USED".equals(uc.getStatus())) {
            return;
        }
        int updated = userCouponMapper.update(null,
                new com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper<UserCoupon>()
                        .eq(UserCoupon::getId, uc.getId())
                        .eq(UserCoupon::getStatus, "USED")
                        .eq(uc.getUsedOrderId() != null, UserCoupon::getUsedOrderId, uc.getUsedOrderId())
                        .isNull(uc.getUsedOrderId() == null, UserCoupon::getUsedOrderId)
                        .set(UserCoupon::getStatus, "UNUSED")
                        .set(UserCoupon::getUsedOrderId, null)
                        .set(UserCoupon::getUsedAt, null));
        if (updated != 1) {
            throw new BizException(2209, "优惠券使用状态已变化，回退失败");
        }
    }

    /** 下单前可用券预览（结算页展示） */
    public List<Map<String, Object>> usableCouponsFor(Long userId, BigDecimal subtotal) {
        LocalDateTime now = LocalDateTime.now();
        List<UserCoupon> mine = userCouponMapper.selectList(new LambdaQueryWrapper<UserCoupon>()
                .eq(UserCoupon::getUserId, userId)
                .eq(UserCoupon::getStatus, "UNUSED")
                .gt(UserCoupon::getExpireAt, now));
        if (mine.isEmpty()) {
            return List.of();
        }
        Map<Long, MallCoupon> templates = couponMapper.selectBatchIds(
                        mine.stream().map(UserCoupon::getCouponId).distinct().toList())
                .stream().collect(Collectors.toMap(MallCoupon::getId, c -> c));
        List<Map<String, Object>> rows = new ArrayList<>();
        for (UserCoupon uc : mine) {
            MallCoupon c = templates.get(uc.getCouponId());
            if (c == null) {
                continue;
            }
            BigDecimal threshold = c.getMinAmount() == null ? BigDecimal.ZERO : c.getMinAmount();
            boolean usable = subtotal.compareTo(threshold) >= 0;
            Map<String, Object> row = new HashMap<>();
            row.put("userCouponId", uc.getId());
            row.put("name", c.getName());
            row.put("discountValue", c.getDiscountValue());
            row.put("minAmount", c.getMinAmount());
            row.put("expireAt", uc.getExpireAt());
            row.put("usable", usable);
            row.put("discount", usable ? c.getDiscountValue().min(subtotal) : BigDecimal.ZERO);
            rows.add(row);
        }
        return rows;
    }

    // ==================== 管理端 ====================

    public List<MallCoupon> adminCoupons() {
        return couponMapper.selectList(new LambdaQueryWrapper<MallCoupon>()
                .orderByDesc(MallCoupon::getId));
    }

    @Transactional
    public Long createCoupon(CouponSaveRequest req) {
        validateCoupon(req);
        MallCoupon c = new MallCoupon();
        copyCoupon(req, c);
        if (c.getValidDays() == null || c.getValidDays() <= 0) {
            c.setValidDays(7);
        }
        c.setReceivedCount(0);
        if (c.getStatus() == null) {
            c.setStatus("ENABLE");
        }
        couponMapper.insert(c);
        return c.getId();
    }

    @Transactional
    public void updateCoupon(Long id, CouponSaveRequest req) {
        MallCoupon exists = couponMapper.selectById(id);
        if (exists == null) {
            throw new BizException(2201, "优惠券不存在");
        }
        MallCoupon upd = new MallCoupon();
        upd.setId(id);
        if (req.getName() != null) upd.setName(req.getName().trim());
        if (req.getDiscountValue() != null) upd.setDiscountValue(req.getDiscountValue());
        if (req.getMinAmount() != null) upd.setMinAmount(req.getMinAmount());
        if (req.getTotalCount() != null) upd.setTotalCount(req.getTotalCount());
        if (req.getStatus() != null) upd.setStatus(req.getStatus());
        if (req.getStartTime() != null) upd.setStartTime(req.getStartTime());
        if (req.getEndTime() != null) upd.setEndTime(req.getEndTime());
        if (req.getValidDays() != null) upd.setValidDays(req.getValidDays());
        var guard = new com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper<MallCoupon>()
                .eq(MallCoupon::getId, id);
        if (req.getTotalCount() != null) {
            if (req.getTotalCount() <= 0) {
                throw new BizException(2001, "发行量必须大于0");
            }
            // Compare against the current database count, not the earlier template snapshot.
            guard.le(MallCoupon::getReceivedCount, req.getTotalCount());
        }
        if (couponMapper.update(upd, guard) != 1) {
            throw new BizException(2001, "发行量不能小于已领取数量或优惠券已变化");
        }
    }

    @Transactional
    public void deleteCoupon(Long id) {
        long received = userCouponMapper.selectCount(new LambdaQueryWrapper<UserCoupon>()
                .eq(UserCoupon::getCouponId, id));
        if (received > 0) {
            throw new BizException(2210, "已有用户领取，不能删除（可下架）");
        }
        couponMapper.deleteById(id);
    }

    public List<MallSeckill> adminSeckills() {
        return seckillMapper.selectList(new LambdaQueryWrapper<MallSeckill>()
                .orderByDesc(MallSeckill::getId));
    }

    @Transactional
    public Long createSeckill(SeckillSaveRequest req) {
        validateSeckillReq(req);
        MallSeckill s = new MallSeckill();
        copySeckill(req, s);
        if (s.getStatus() == null) {
            s.setStatus("ENABLE");
        }
        if (s.getSeckillLimit() == null || s.getSeckillLimit() <= 0) {
            s.setSeckillLimit(1);
        }
        seckillMapper.insert(s);
        return s.getId();
    }

    @Transactional
    public void updateSeckill(Long id, SeckillSaveRequest req) {
        MallSeckill exists = seckillMapper.selectById(id);
        if (exists == null) {
            throw new BizException(2206, "秒杀活动不存在");
        }
        MallSeckill upd = new MallSeckill();
        upd.setId(id);
        if (req.getSeckillPrice() != null) upd.setSeckillPrice(req.getSeckillPrice());
        if (req.getSeckillStock() != null) upd.setSeckillStock(req.getSeckillStock());
        if (req.getSeckillLimit() != null) upd.setSeckillLimit(req.getSeckillLimit());
        if (req.getStartTime() != null) upd.setStartTime(req.getStartTime());
        if (req.getEndTime() != null) upd.setEndTime(req.getEndTime());
        if (req.getStatus() != null) upd.setStatus(req.getStatus());
        if (req.getStartTime() != null || req.getEndTime() != null) {
            LocalDateTime start = req.getStartTime() != null ? req.getStartTime() : exists.getStartTime();
            LocalDateTime end = req.getEndTime() != null ? req.getEndTime() : exists.getEndTime();
            if (!start.isBefore(end)) {
                throw new BizException(2001, "活动开始时间必须早于结束时间");
            }
        }
        seckillMapper.updateById(upd);
    }

    @Transactional
    public void deleteSeckill(Long id) {
        seckillMapper.deleteById(id);
    }

    // ==================== 内部工具 ====================

    private UserCoupon requireUsableCoupon(Long userId, Long couponUserId) {
        UserCoupon uc = userCouponMapper.selectById(couponUserId);
        if (uc == null || uc.getDeleted() != null && uc.getDeleted() == 1) {
            throw new BizException(2201, "优惠券不存在");
        }
        if (!uc.getUserId().equals(userId)) {
            throw new BizException(2003, "无权使用该优惠券");
        }
        if (!"UNUSED".equals(uc.getStatus())) {
            throw new BizException(2209, "优惠券不可用（已使用或已过期）");
        }
        if (uc.getExpireAt() != null && LocalDateTime.now().isAfter(uc.getExpireAt())) {
            throw new BizException(2209, "优惠券已过期");
        }
        return uc;
    }

    /** 用户券对外状态：未过期未用=UNUSED，过期=EXPIRED */
    private String resolveStatus(UserCoupon uc) {
        if ("USED".equals(uc.getStatus())) {
            return "USED";
        }
        return uc.getExpireAt() != null && LocalDateTime.now().isAfter(uc.getExpireAt())
                ? "EXPIRED" : uc.getStatus();
    }

    private Map<String, Object> couponView(MallCoupon c, boolean received) {
        Map<String, Object> row = new HashMap<>();
        row.put("couponId", c.getId());
        row.put("name", c.getName());
        row.put("discountValue", c.getDiscountValue());
        row.put("minAmount", c.getMinAmount());
        row.put("totalCount", c.getTotalCount());
        row.put("receivedCount", c.getReceivedCount());
        row.put("startTime", c.getStartTime());
        row.put("endTime", c.getEndTime());
        row.put("received", received);
        return row;
    }

    private void validateCoupon(CouponSaveRequest req) {
        if (req.getName() == null || req.getName().isBlank()) {
            throw new BizException(2001, "券名称不能为空");
        }
        if (req.getDiscountValue() == null || req.getDiscountValue().signum() <= 0) {
            throw new BizException(2001, "优惠金额必须大于0");
        }
        if (req.getTotalCount() == null || req.getTotalCount() <= 0) {
            throw new BizException(2001, "发行量必须大于0");
        }
        if (req.getStartTime() != null && req.getEndTime() != null
                && !req.getStartTime().isBefore(req.getEndTime())) {
            throw new BizException(2001, "领取开始时间必须早于结束时间");
        }
    }

    private void copyCoupon(CouponSaveRequest req, MallCoupon c) {
        c.setName(req.getName().trim());
        c.setDiscountValue(req.getDiscountValue());
        c.setMinAmount(req.getMinAmount() == null ? BigDecimal.ZERO : req.getMinAmount());
        c.setTotalCount(req.getTotalCount());
        c.setStartTime(req.getStartTime());
        c.setEndTime(req.getEndTime());
        c.setValidDays(req.getValidDays());
        c.setStatus(req.getStatus());
    }

    private void validateSeckillReq(SeckillSaveRequest req) {
        if (req.getProductId() == null) {
            throw new BizException(2001, "秒杀商品不能为空");
        }
        Product p = productMapper.selectById(req.getProductId());
        if (p == null) {
            throw new BizException(2002, "秒杀商品不存在");
        }
        if (req.getSeckillPrice() == null || req.getSeckillPrice().signum() <= 0) {
            throw new BizException(2001, "秒杀价必须大于0");
        }
        if (req.getSeckillStock() == null || req.getSeckillStock() <= 0) {
            throw new BizException(2001, "秒杀库存必须大于0");
        }
        if (req.getStartTime() == null || req.getEndTime() == null || !req.getStartTime().isBefore(req.getEndTime())) {
            throw new BizException(2001, "活动时间窗无效");
        }
    }

    private void copySeckill(SeckillSaveRequest req, MallSeckill s) {
        s.setProductId(req.getProductId());
        s.setSeckillPrice(req.getSeckillPrice());
        s.setSeckillStock(req.getSeckillStock());
        s.setSeckillLimit(req.getSeckillLimit());
        s.setStartTime(req.getStartTime());
        s.setEndTime(req.getEndTime());
        s.setStatus(req.getStatus());
    }

    // ==================== 请求体 ====================

    @lombok.Data
    public static class CouponSaveRequest {
        private String name;
        private BigDecimal discountValue;
        private BigDecimal minAmount;
        private Integer totalCount;
        private String status;
        private LocalDateTime startTime;
        private LocalDateTime endTime;
        private Integer validDays;
    }

    @lombok.Data
    public static class SeckillSaveRequest {
        private Long productId;
        private BigDecimal seckillPrice;
        private Integer seckillStock;
        private Integer seckillLimit;
        private LocalDateTime startTime;
        private LocalDateTime endTime;
        private String status;
    }
}
