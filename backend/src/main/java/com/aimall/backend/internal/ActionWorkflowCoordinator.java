package com.aimall.backend.internal;

import com.aimall.backend.common.BizException;
import com.aimall.backend.common.RequestBudget;
import java.time.Duration;
import com.aimall.backend.config.AppProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.LinkedHashMap;
import java.util.Map;

/** Deliberately non-transactional: canonical reads/prepare commits finish before any AI call. */
@Service
@RequiredArgsConstructor
public class ActionWorkflowCoordinator {
    private final AgentOrderActionService actions;
    private final ActionWorkflowClient client;
    private final AppProperties props;

    public boolean enabled() { return props.getAi().isActionWorkflowsEnabled(); }

    public boolean requiresNative(Long userId, String actionId) {
        if (enabled()) return true;
        if (actions.isNativeManaged(userId, actionId))
            throw new BizException(5002, "此操作由原生工作流管理，请启用工作流后恢复，不能直接确认或取消");
        return false;
    }

    public void validatePreparationKey(String key) {
        if (enabled() && (key == null || key.isBlank())) throw new BizException(2001, "原生操作缺少 preparationKey");
        if (!enabled() && key != null) throw new BizException(2004, "原生操作功能开关不一致");
    }

    public void rejectLegacyConfirm(Long userId, String actionId) {
        if (enabled() || actions.isNativeManaged(userId, actionId))
            throw new BizException(2004, "请通过买家确认接口和原生工作流处理操作");
    }

    public Map<String, Object> start(Long userId, String actionId) {
        return invoke(userId, actionId, "start", null, null);
    }
    public Map<String, Object> confirm(Long userId, String actionId, AgentOrderActionService.ApprovalRequest approval) {
        return invoke(userId, actionId, "resume", "approve", approval);
    }
    public Map<String, Object> cancel(Long userId, String actionId) {
        return invoke(userId, actionId, "resume", "reject", null);
    }
    public Map<String, Object> recover(Long userId, String actionId) {
        return invoke(userId, actionId, "recover", null, null);
    }

    public void requireEnabled() {
        if (!enabled()) throw new BizException(5002, "原生工作流未启用；不能绕过已保存的操作决策");
    }

    private Map<String, Object> invoke(Long userId, String actionId, String operation, String decision,
                                       AgentOrderActionService.ApprovalRequest approval) {
        requireEnabled();
        if (TransactionSynchronizationManager.isActualTransactionActive())
            throw new IllegalStateException("Native coordination cannot hold a business transaction");
        try (var ignored = RequestBudget.open(Duration.ofSeconds(30),RequestBudget.MAX_RETRY_BUDGET)) {
            return invokeWithinDeadline(userId,actionId,operation,decision,approval);
        }
    }

    private Map<String, Object> invokeWithinDeadline(Long userId, String actionId, String operation, String decision,
                                                     AgentOrderActionService.ApprovalRequest approval) {
        var snapshot = actions.snapshot(userId, actionId);
        if (!"PENDING".equals(snapshot.status()) && !actions.isNativeManaged(userId, actionId))
            throw new BizException(2004, "非待确认的旧操作不能创建原生工作流");
        actions.markNativeManaged(userId, actionId);
        // Register lost/legacy pending workflows; existing checkpoints (including terminal ones) are read idempotently.
        if (!"start".equals(operation)) client.invoke(snapshot, "start", null, null);
        var response = client.invoke(snapshot, operation, decision, approval);
        var result = new LinkedHashMap<String, Object>();
        if (response.result() != null) result.putAll(response.result());
        var metadata = new LinkedHashMap<String, Object>();
        metadata.put("actionId", response.actionId()); metadata.put("workflowStatus", response.workflowStatus());
        metadata.put("nativeInterrupt", response.nativeInterrupt()); metadata.put("interrupted", response.interrupted());
        metadata.put("recoverable", response.recoverable());
        if (response.error() != null) metadata.put("error", response.error());
        result.put("workflow", metadata);
        return result;
    }
}
