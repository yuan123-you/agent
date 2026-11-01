package com.aimall.backend.internal;

import com.aimall.backend.config.AppProperties;
import com.aimall.backend.common.RequestBudget;
import reactor.core.publisher.Mono;
import java.io.IOException;
import java.util.concurrent.TimeoutException;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/** One HTTP attempt only. Durable execution retries belong exclusively to the Python graph. */
@Component
public class ActionWorkflowClient {
    private static final Set<String> STATUSES = Set.of("WAITING_APPROVAL", "EXECUTING", "COMPLETED", "CANCELLED", "FAILED", "EXPIRED");
    private final WebClient webClient;
    private final AppProperties props;

    public ActionWorkflowClient(WebClient aiWebClient, AppProperties props) {
        this.webClient = aiWebClient;
        this.props = props;
    }

    public record WorkflowResult(String actionId, String workflowStatus, boolean nativeInterrupt,
                                 boolean interrupted, boolean recoverable, Map<String, Object> result,
                                 Map<String, Object> error) {}

    public enum FailureKind { AUTHORIZATION, PERMANENT_HTTP, TRANSIENT_HTTP, TRANSPORT, DEADLINE, INVALID_RESPONSE, PERMANENT_CLIENT }

    /** Does not retain/log the upstream body, which may contain private delivery information. */
    public static class GatewayException extends RuntimeException {
        private final String actionId;
        private final int status;
        private final boolean recoverable;
        private final FailureKind failureKind;
        public GatewayException(String actionId, int status, boolean recoverable) {
            this(actionId,status,recoverable,FailureKind.TRANSPORT);
        }
        public GatewayException(String actionId, int status, boolean recoverable, FailureKind failureKind) {
            super("Native action workflow unavailable; use recovery without changing the saved approval");
            this.actionId = actionId; this.status = status; this.recoverable = recoverable; this.failureKind = failureKind;
        }
        public String actionId() { return actionId; }
        public int status() { return status; }
        public boolean recoverable() { return recoverable; }
        public FailureKind failureKind() { return failureKind; }
    }

    public WorkflowResult invoke(AgentOrderActionService.ActionSnapshot snapshot, String operation, String decision,
                                 AgentOrderActionService.ApprovalRequest approval) {
        if (TransactionSynchronizationManager.isActualTransactionActive())
            throw new IllegalStateException("AI HTTP must not run inside a business transaction");
        if (!Set.of("start", "status", "recover", "resume").contains(operation)) throw new IllegalArgumentException("operation");
        var body = new LinkedHashMap<String, Object>();
        body.put("userId", snapshot.userId()); body.put("conversationId", snapshot.conversationId());
        if ("resume".equals(operation)) {
            if (!Set.of("approve", "reject").contains(decision)) throw new IllegalArgumentException("decision");
            body.put("decision", decision);
            if (approval != null) body.put("approval", approval);
        } else if (decision != null || approval != null) throw new IllegalArgumentException("No decision allowed for " + operation);
        var budget = RequestBudget.forOperation(Duration.ofSeconds(30));
        try {
            WorkflowResult response = Mono.defer(() -> webClient.post().uri("/v1/action-workflows/{actionId}/{operation}", snapshot.actionId(), operation)
                    .header("X-Internal-Token", props.getAi().getInternalToken())
                    .headers(budget::writeHeaders)
                    .contentType(MediaType.APPLICATION_JSON).bodyValue(body).retrieve()
                    .bodyToMono(WorkflowResult.class).timeout(budget.remainingTimeout()))
                    .block(budget.remainingTimeout());
            if (response == null || !snapshot.actionId().equals(response.actionId()) || !response.nativeInterrupt()
                    || !STATUSES.contains(response.workflowStatus() == null ? "" : response.workflowStatus())
                    || ("COMPLETED".equals(response.workflowStatus()) && response.result() == null))
                throw new GatewayException(snapshot.actionId(), 503, true, FailureKind.INVALID_RESPONSE);
            if (response.result() != null) {
                boolean completed = "COMPLETED".equals(response.workflowStatus());
                boolean cancelled = "CANCELLED".equals(response.workflowStatus());
                if ((!completed && !cancelled) || !snapshot.type().equals(response.result().get("type"))
                        || !(completed ? "CONFIRMED" : "CANCELLED").equals(response.result().get("actionStatus")))
                    throw new GatewayException(snapshot.actionId(), 503, true, FailureKind.INVALID_RESPONSE);
            }
            return response;
        } catch (GatewayException e) { throw e; }
        catch (WebClientResponseException e) {
            int status = e.getStatusCode().value();
            boolean transientHttp = Set.of(408,429,500,502,503,504).contains(status);
            FailureKind kind = status==401 || status==403 ? FailureKind.AUTHORIZATION
                    : transientHttp ? FailureKind.TRANSIENT_HTTP : FailureKind.PERMANENT_HTTP;
            throw new GatewayException(snapshot.actionId(), status >= 500 ? 503 : status, transientHttp, kind);
        } catch (Exception e) {
            Throwable cause = e;
            while (cause.getCause()!=null) cause=cause.getCause();
            FailureKind kind = e instanceof org.springframework.core.codec.CodecException ? FailureKind.INVALID_RESPONSE
                    : cause instanceof RequestBudget.DeadlineExceeded || cause instanceof TimeoutException ? FailureKind.DEADLINE
                    : cause instanceof IOException && !(cause instanceof javax.net.ssl.SSLException)
                    && !(cause instanceof java.net.ProtocolException) ? FailureKind.TRANSPORT : FailureKind.PERMANENT_CLIENT;
            // Recoverable means explicit durable recovery, never permission to replay this HTTP call.
            throw new GatewayException(snapshot.actionId(), 503, true, kind);
        }
    }
}
