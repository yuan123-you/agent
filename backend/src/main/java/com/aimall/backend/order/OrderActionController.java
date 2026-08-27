package com.aimall.backend.order;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.internal.AgentOrderActionService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/** Buyer-owned explicit decision endpoints for prepared AI order actions. */
@RestController
@RequestMapping("/api/v1/order-actions")
@RequiredArgsConstructor
public class OrderActionController {
    private final AgentOrderActionService actionService;

    @PostMapping("/{actionId}/confirm")
    public ApiResponse<Map<String, Object>> confirm(@AuthenticationPrincipal Long userId,
                                                    @PathVariable String actionId,
                                                    @Valid @RequestBody(required = false)
                                                    AgentOrderActionService.ApprovalRequest approval) {
        String type = actionService.typeOf(userId, actionId);
        Map<String, Object> result = new LinkedHashMap<>();
        if (AgentOrderActionService.ORDER_CREATE.equals(type)) {
            OrderInfo order = actionService.confirm(userId, actionId, approval);
            result.put("type", type); result.put("actionStatus", "CONFIRMED");
            result.put("orderId", order.getId()); result.put("orderNo", order.getOrderNo());
            result.put("status", order.getStatus()); result.put("totalAmount", order.getTotalAmount());
        } else {
            var confirmed = actionService.confirmBusiness(userId, actionId);
            result.put("type", confirmed.type()); result.put("actionStatus", confirmed.status());
            result.put("orderId", confirmed.orderId()); result.put("orderNo", confirmed.orderNo());
            result.put("status", confirmed.orderStatus());
            result.put("afterSaleId", confirmed.afterSaleId()); result.put("afterSaleNo", confirmed.afterSaleNo());
        }
        return ApiResponse.ok(result);
    }

    @GetMapping("/{actionId}")
    public ApiResponse<AgentOrderActionService.ActionStatusResult> status(
            @AuthenticationPrincipal Long userId, @PathVariable String actionId) {
        return ApiResponse.ok(actionService.status(userId, actionId));
    }

    @PostMapping("/{actionId}/cancel")
    public ApiResponse<Void> cancel(@AuthenticationPrincipal Long userId,
                                    @PathVariable String actionId) {
        actionService.cancel(userId, actionId);
        return ApiResponse.ok();
    }
}
