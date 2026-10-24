package com.aimall.backend.order;

import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 自动确认收货：发货满 7 天仍未确认的订单，定时批量推进为已完成（DELIVERED）。
 * 对标 mall 的 auto_confirm_day；逐单走状态机（含乐观校验），失败不影响其余订单。
 */
@Component
@Slf4j
@RequiredArgsConstructor
public class OrderAutoConfirmJob {

    private final OrderInfoMapper orderInfoMapper;
    private final OrderService orderService;

    private static final int AUTO_CONFIRM_DAYS = 7;
    private static final int BATCH_LIMIT = 200;

    /** 每 30 分钟扫描一次（演示环境低频足够；商品演示无真实物流，主要兜底长尾订单） */
    @Scheduled(fixedDelayString = "PT30M", initialDelayString = "PT2M")
    public void autoConfirmDelivered() {
        LocalDateTime threshold = LocalDateTime.now().minusDays(AUTO_CONFIRM_DAYS);
        List<OrderInfo> overdue = orderInfoMapper.selectList(new LambdaQueryWrapper<OrderInfo>()
                .eq(OrderInfo::getStatus, "SHIPPED")
                .le(OrderInfo::getShippedAt, threshold)
                .last("LIMIT " + BATCH_LIMIT));
        if (overdue.isEmpty()) {
            return;
        }
        int ok = 0;
        for (OrderInfo order : overdue) {
            try {
                orderService.deliver(order.getId());
                ok++;
            } catch (Exception e) {
                // 单笔失败（并发状态变化）跳过，下一轮重扫
                log.warn("auto confirm skipped orderId={}: {}", order.getId(), e.getMessage());
            }
        }
        log.info("auto confirm delivered: scanned={}, confirmed={}", overdue.size(), ok);
    }
}
