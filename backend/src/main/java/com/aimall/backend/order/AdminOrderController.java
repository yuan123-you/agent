package com.aimall.backend.order;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 管理端订单接口：/api/v1/admin/orders（仅 ADMIN）
 */
@RestController
@RequestMapping("/api/v1/admin/orders")
@RequiredArgsConstructor
public class AdminOrderController {

    private final OrderService orderService;
    private final UserMapper userMapper;

    @GetMapping
    public ApiResponse<PageResult<Map<String, Object>>> list(
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        Page<OrderInfo> result = orderService.adminList(status, page, size);
        // 批量补买家昵称
        List<Long> userIds = result.getRecords().stream().map(OrderInfo::getUserId).distinct().toList();
        Map<Long, String> nicknameMap = new HashMap<>();
        if (!userIds.isEmpty()) {
            for (User u : userMapper.selectList(new LambdaQueryWrapper<User>().in(User::getId, userIds))) {
                nicknameMap.put(u.getId(), u.getNickname());
            }
        }
        return ApiResponse.ok(PageResult.of(result, o -> {
            Map<String, Object> vo = new HashMap<>();
            vo.put("orderId", o.getId());
            vo.put("orderNo", o.getOrderNo());
            vo.put("userId", o.getUserId());
            vo.put("userNickname", nicknameMap.getOrDefault(o.getUserId(), "-"));
            vo.put("status", o.getStatus());
            vo.put("totalAmount", o.getTotalAmount());
            vo.put("source", o.getSource());
            vo.put("logisticsNo", o.getLogisticsNo());
            vo.put("createdAt", o.getCreatedAt());
            vo.put("items", orderService.itemsOf(o.getId()));
            return vo;
        }));
    }

    @PostMapping("/{id}/ship")
    public ApiResponse<Void> ship(@PathVariable Long id, @RequestBody Map<String, String> body) {
        String logisticsNo = body.get("logisticsNo");
        if (logisticsNo == null || logisticsNo.isBlank()) {
            logisticsNo = "SF" + System.currentTimeMillis();
        }
        orderService.ship(id, logisticsNo);
        return ApiResponse.ok();
    }

    @PostMapping("/{id}/deliver")
    public ApiResponse<Void> deliver(@PathVariable Long id) {
        orderService.deliver(id);
        return ApiResponse.ok();
    }
}
