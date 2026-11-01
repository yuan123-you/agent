package com.aimall.backend.internal;

import com.aimall.backend.common.BizException;
import com.aimall.backend.config.AppProperties;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.Map;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ActionWorkflowCoordinatorTest {
    private final AgentOrderActionService service = mock(AgentOrderActionService.class);
    private final ActionWorkflowClient client = mock(ActionWorkflowClient.class);
    private final AppProperties props = new AppProperties();
    private final ActionWorkflowCoordinator coordinator = new ActionWorkflowCoordinator(service, client, props);
    private final AgentOrderActionService.ActionSnapshot snapshot = new AgentOrderActionService.ActionSnapshot(
            "act", 7L, 20L, "ORDER_CREATE", "PENDING", Instant.parse("2026-11-01T12:00:00Z"), "fingerprint");
    private ActionWorkflowClient.WorkflowResult response(String status, Map<String,Object> result) {
        return new ActionWorkflowClient.WorkflowResult("act", status, true, "WAITING_APPROVAL".equals(status), true, result, null);
    }
    private void enabled() { props.getAi().setActionWorkflowsEnabled(true); when(service.snapshot(7L,"act")).thenReturn(snapshot); }

    @Test void defaultsOffAndNativeProvenanceFailsClosedAfterFlagSwitch() {
        assertFalse(coordinator.enabled());
        assertFalse(coordinator.requiresNative(7L,"legacy"));
        when(service.isNativeManaged(7L,"act")).thenReturn(true);
        assertThrows(BizException.class, () -> coordinator.requiresNative(7L,"act"));
        assertThrows(BizException.class, () -> coordinator.recover(7L,"act"));
        verifyNoInteractions(client);
    }
    @Test void preparationFlagMismatchCannotCreateUnmanagedOrUnkeyedNativeActions() {
        assertThrows(BizException.class, () -> coordinator.validatePreparationKey("call"));
        coordinator.validatePreparationKey(null);
        props.getAi().setActionWorkflowsEnabled(true);
        assertThrows(BizException.class, () -> coordinator.validatePreparationKey(null));
        assertThrows(BizException.class, () -> coordinator.validatePreparationKey(""));
        coordinator.validatePreparationKey("call");
    }
    @Test void trustedApprovalResumesAndMapsLegacyReceiptWithWorkflowMetadata() {
        enabled();
        var approval = new AgentOrderActionService.ApprovalRequest("Edited", "13900000000", "New address");
        when(client.invoke(snapshot,"resume","approve",approval)).thenReturn(response("COMPLETED", Map.of(
                "type","ORDER_CREATE","actionStatus","CONFIRMED","orderId",88L,"receiverName","Edited")));
        var receipt = coordinator.confirm(7L,"act",approval);
        assertEquals(88L, receipt.get("orderId"));
        assertEquals("Edited", receipt.get("receiverName"));
        assertEquals("COMPLETED", ((Map<?,?>)receipt.get("workflow")).get("workflowStatus"));
        verify(service,never()).confirm(anyLong(),anyString(),any());
        verify(service,never()).confirmBusiness(anyLong(),anyString());
    }
    @Test void rejectOnlyResumesGraphAndRecoverDoesNotInventApproval() {
        enabled();
        when(client.invoke(snapshot,"resume","reject",null)).thenReturn(response("CANCELLED", Map.of("type","ORDER_CREATE","actionStatus","CANCELLED")));
        coordinator.cancel(7L,"act");
        when(client.invoke(snapshot,"recover",null,null)).thenReturn(response("WAITING_APPROVAL",null));
        var waiting = coordinator.recover(7L,"act");
        assertFalse(waiting.containsKey("actionStatus"));
        when(client.invoke(snapshot,"recover",null,null)).thenReturn(response("EXECUTING",null));
        assertEquals("EXECUTING", ((Map<?,?>)coordinator.recover(7L,"act").get("workflow")).get("workflowStatus"));
        verify(service,never()).cancel(anyLong(),anyString());
        verify(service,never()).confirm(anyLong(),anyString(),any());
    }
    @Test void ownerAndCanonicalValidationHappenBeforeAnyGatewayRequest() {
        enabled(); when(service.snapshot(8L,"act")).thenThrow(new BizException(2003,"forbidden"));
        assertThrows(BizException.class, () -> coordinator.confirm(8L,"act",null));
        assertThrows(BizException.class, () -> coordinator.recover(8L,"act"));
        verifyNoInteractions(client);
    }
    @Test void gatewayFailureIsRecoverableWithNoDirectConfirmationFallback() {
        enabled(); when(client.invoke(snapshot,"resume","approve",null)).thenThrow(new ActionWorkflowClient.GatewayException("act",503,true));
        var error = assertThrows(ActionWorkflowClient.GatewayException.class, () -> coordinator.confirm(7L,"act",null));
        assertTrue(error.recoverable());
        verify(service,never()).confirm(anyLong(),anyString(),any());
    }
    @Test void startAndRecoverNeverSendDecisionAndRefuseAmbientBusinessTransaction() {
        enabled(); when(client.invoke(snapshot,"start",null,null)).thenReturn(response("WAITING_APPROVAL",null));
        coordinator.start(7L,"act"); verify(client).invoke(snapshot,"start",null,null);
        TransactionSynchronizationManager.setActualTransactionActive(true);
        try { assertThrows(IllegalStateException.class, () -> coordinator.recover(7L,"act")); }
        finally { TransactionSynchronizationManager.setActualTransactionActive(false); }
        verify(client,never()).invoke(snapshot,"recover",null,null);
    }
    @Test void registrationPrecedesApproveRejectAndWaitingRecoveryWithoutDirectEffects() {
        enabled();
        var approval = new AgentOrderActionService.ApprovalRequest("Edited", "13900000000", "New address");
        when(client.invoke(snapshot,"start",null,null)).thenReturn(response("WAITING_APPROVAL",null));
        when(client.invoke(snapshot,"resume","approve",approval)).thenReturn(response("EXECUTING",null));
        when(client.invoke(snapshot,"resume","reject",null)).thenReturn(response("CANCELLED",null));
        when(client.invoke(snapshot,"recover",null,null)).thenReturn(response("WAITING_APPROVAL",null));

        coordinator.confirm(7L,"act",approval);
        coordinator.cancel(7L,"act");
        var waiting = coordinator.recover(7L,"act");

        var ordered = inOrder(service,client);
        ordered.verify(service).snapshot(7L,"act");
        ordered.verify(service).markNativeManaged(7L,"act");
        ordered.verify(client).invoke(snapshot,"start",null,null);
        ordered.verify(client).invoke(snapshot,"resume","approve",approval);
        ordered.verify(service).snapshot(7L,"act");
        ordered.verify(service).markNativeManaged(7L,"act");
        ordered.verify(client).invoke(snapshot,"start",null,null);
        ordered.verify(client).invoke(snapshot,"resume","reject",null);
        ordered.verify(service).snapshot(7L,"act");
        ordered.verify(service).markNativeManaged(7L,"act");
        ordered.verify(client).invoke(snapshot,"start",null,null);
        ordered.verify(client).invoke(snapshot,"recover",null,null);
        verifyNoMoreInteractions(service,client);
        assertEquals("WAITING_APPROVAL",((Map<?,?>)waiting.get("workflow")).get("workflowStatus"));
        assertFalse(waiting.containsKey("actionStatus"));
        assertFalse(waiting.containsKey("orderId"));
    }

    @Test void registrationFailureDoesNotRetryResumeRecoverOrExecuteDomainEffects() {
        enabled();
        when(client.invoke(snapshot,"start",null,null)).thenThrow(new ActionWorkflowClient.GatewayException("act",503,true));

        assertThrows(ActionWorkflowClient.GatewayException.class, () -> coordinator.confirm(7L,"act",null));
        assertThrows(ActionWorkflowClient.GatewayException.class, () -> coordinator.cancel(7L,"act"));
        assertThrows(ActionWorkflowClient.GatewayException.class, () -> coordinator.recover(7L,"act"));

        verify(service,times(3)).snapshot(7L,"act");
        verify(service,times(3)).markNativeManaged(7L,"act");
        verify(client,times(3)).invoke(snapshot,"start",null,null);
        verifyNoMoreInteractions(service,client);
    }

    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(strings={"CONFIRMED","CANCELLED","EXPIRED"})
    void existingTerminalCheckpointCanBeRecoveredEvenWhenCanonicalActionIsNoLongerPending(String status) {
        enabled();
        var canonical = new AgentOrderActionService.ActionSnapshot("act",7L,20L,"ORDER_CREATE",status,
                snapshot.expiresAt(),snapshot.fingerprint());
        when(service.snapshot(7L,"act")).thenReturn(canonical);
        when(service.isNativeManaged(7L,"act")).thenReturn(true);
        String workflowStatus="CONFIRMED".equals(status) ? "COMPLETED" : status;
        Map<String,Object> result="CONFIRMED".equals(status)
                ? Map.of("type","ORDER_CREATE","actionStatus","CONFIRMED","orderId",88L)
                : "CANCELLED".equals(status) ? Map.of("type","ORDER_CREATE","actionStatus","CANCELLED") : null;
        var receipt = response(workflowStatus,result);
        when(client.invoke(canonical,"start",null,null)).thenReturn(receipt);
        when(client.invoke(canonical,"recover",null,null)).thenReturn(receipt);

        var recovered=coordinator.recover(7L,"act");
        assertEquals(workflowStatus,((Map<?,?>)recovered.get("workflow")).get("workflowStatus"));
        if ("CONFIRMED".equals(status)) assertEquals(88L,recovered.get("orderId"));

        var ordered = inOrder(service,client);
        ordered.verify(service).snapshot(7L,"act");
        ordered.verify(service).isNativeManaged(7L,"act");
        ordered.verify(service).markNativeManaged(7L,"act");
        ordered.verify(client).invoke(canonical,"start",null,null);
        ordered.verify(client).invoke(canonical,"recover",null,null);
        verifyNoMoreInteractions(service,client);
    }

    @Test void terminalLegacyActionIsRejectedBeforeProvenanceOrGateway() {
        enabled();
        for (String status : new String[]{"CONFIRMED","CANCELLED","EXPIRED"}) {
            var canonical = new AgentOrderActionService.ActionSnapshot("act",7L,20L,"ORDER_CREATE",status,
                    snapshot.expiresAt(),snapshot.fingerprint());
            when(service.snapshot(7L,"act")).thenReturn(canonical);
            var error=assertThrows(BizException.class, () -> coordinator.recover(7L,"act"));
            assertEquals(2004,error.getCode());
        }
        verify(service,times(3)).snapshot(7L,"act");
        verify(service,times(3)).isNativeManaged(7L,"act");
        verifyNoMoreInteractions(service);
        verifyNoInteractions(client);
    }

    @Test void preparationStartAlsoPersistsProvenanceBeforeGatewayAndWriteFailureNeverStarts() {
        enabled();
        when(client.invoke(snapshot,"start",null,null)).thenReturn(response("WAITING_APPROVAL",null));
        coordinator.start(7L,"act");
        var ordered=inOrder(service,client);
        ordered.verify(service).snapshot(7L,"act");
        ordered.verify(service).markNativeManaged(7L,"act");
        ordered.verify(client).invoke(snapshot,"start",null,null);
        clearInvocations(service,client);
        doThrow(new BizException(2004,"provenance write failed")).when(service).markNativeManaged(7L,"act");
        assertThrows(BizException.class,()->coordinator.recover(7L,"act"));
        verifyNoInteractions(client);
    }

}
