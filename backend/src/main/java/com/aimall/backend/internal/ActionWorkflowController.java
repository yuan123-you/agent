package com.aimall.backend.internal;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.ExactNumberDeserializers;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import java.util.LinkedHashMap;
import java.util.Map;

/** Internal-token protected callbacks. Only native graph execution uses these domain mutation routes. */
@RestController
@RequestMapping("/internal/tools/action-workflows")
@RequiredArgsConstructor
public class ActionWorkflowController {
    private final AgentOrderActionService actions;
    private final ActionWorkflowCoordinator workflows;

    public record ActionBody(@JsonDeserialize(using = ExactNumberDeserializers.LongValue.class) Long userId, String actionId) {
        @JsonAnySetter
        public void rejectUnknown(String key, Object value) { throw new IllegalArgumentException("Unknown workflow field"); }
    }
    public record ExecuteBody(@JsonDeserialize(using = ExactNumberDeserializers.LongValue.class) Long userId, String actionId,
                              AgentOrderActionService.ApprovalRequest approval) {
        @JsonAnySetter
        public void rejectUnknown(String key, Object value) { throw new IllegalArgumentException("Unknown workflow field"); }
    }

    @PostMapping("/snapshot")
    public ApiResponse<AgentOrderActionService.ActionSnapshot> snapshot(@RequestBody ActionBody body) {
        workflows.requireEnabled();
        return ApiResponse.ok(actions.snapshot(body.userId(), body.actionId()));
    }

    @PostMapping("/execute")
    public ApiResponse<Map<String, Object>> execute(@RequestBody ExecuteBody body) {
        workflows.requireEnabled();
        var snapshot = actions.snapshot(body.userId(), body.actionId());
        var result = new LinkedHashMap<String, Object>();
        if (AgentOrderActionService.ORDER_CREATE.equals(snapshot.type())) {
            var order = actions.confirm(body.userId(), body.actionId(), body.approval());
            result.put("type", snapshot.type()); result.put("actionStatus", "CONFIRMED");
            result.put("orderId", order.getId()); result.put("orderNo", order.getOrderNo());
            result.put("status", order.getStatus()); result.put("totalAmount", order.getTotalAmount());
            // Read the committed order, never a stale local form or original preparation address.
            result.put("receiverName", order.getReceiverName()); result.put("receiverPhone", order.getReceiverPhone());
            result.put("receiverAddress", order.getReceiverAddress());
        } else {
            var confirmed = actions.confirmBusiness(body.userId(), body.actionId());
            result.put("type", confirmed.type()); result.put("actionStatus", confirmed.status());
            result.put("orderId", confirmed.orderId()); result.put("orderNo", confirmed.orderNo());
            result.put("status", confirmed.orderStatus()); result.put("afterSaleId", confirmed.afterSaleId());
            result.put("afterSaleNo", confirmed.afterSaleNo());
        }
        return ApiResponse.ok(result);
    }

    @PostMapping("/cancel")
    public ApiResponse<Map<String, Object>> cancel(@RequestBody ActionBody body) {
        workflows.requireEnabled();
        var snapshot = actions.snapshot(body.userId(), body.actionId());
        actions.cancel(body.userId(), body.actionId());
        return ApiResponse.ok(Map.of("type", snapshot.type(), "actionStatus", "CANCELLED"));
    }
}
