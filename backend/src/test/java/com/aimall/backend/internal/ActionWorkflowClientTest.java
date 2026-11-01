package com.aimall.backend.internal;

import com.aimall.backend.config.AppProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.mock.http.client.reactive.MockClientHttpRequest;
import org.springframework.web.reactive.function.client.*;
import reactor.core.publisher.Mono;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.jupiter.api.Assertions.*;

/** In-memory WebClient ExchangeFunction only: never opens a network socket. */
class ActionWorkflowClientTest {
    private final AgentOrderActionService.ActionSnapshot snapshot = new AgentOrderActionService.ActionSnapshot(
            "act",7L,20L,"ORDER_CREATE","PENDING",Instant.parse("2026-11-01T00:00:00Z"),"hash");
    private final AppProperties props = new AppProperties();
    private ClientResponse response(HttpStatus status,String body) {
        return ClientResponse.create(status).header("Content-Type","application/json").body(body).build();
    }
    @Test void sendsFrozenAuthenticatedJsonAndConsumesNativeResult() throws Exception {
        props.getAi().setInternalToken("local-test-token");
        AtomicReference<ClientRequest> request = new AtomicReference<>();
        var web = WebClient.builder().baseUrl("http://not-used.invalid").exchangeFunction(r -> {
            request.set(r); return Mono.just(response(HttpStatus.OK,"{\"actionId\":\"act\",\"workflowStatus\":\"EXECUTING\",\"nativeInterrupt\":true,\"interrupted\":false,\"recoverable\":true}"));
        }).build();
        var result = new ActionWorkflowClient(web,props).invoke(snapshot,"resume","approve",
                new AgentOrderActionService.ApprovalRequest("Edited","13900000000","Private address"));
        assertEquals("EXECUTING",result.workflowStatus());
        assertEquals("/v1/action-workflows/act/resume",request.get().url().getPath());
        assertEquals("local-test-token",request.get().headers().getFirst("X-Internal-Token"));
        var output = new MockClientHttpRequest(request.get().method(),request.get().url());
        request.get().writeTo(output,ExchangeStrategies.withDefaults()).block();
        var body = new ObjectMapper().readTree(output.getBodyAsString().block());
        assertEquals(7,body.get("userId").intValue()); assertEquals(20,body.get("conversationId").intValue());
        assertEquals("approve",body.get("decision").asText());
        assertEquals("Edited",body.get("approval").get("receiverName").asText());
        assertEquals(4,body.size()); assertFalse(body.has("result"));
    }
    @Test void oneAttemptOn503And409PreservesConflictInsteadOfRetryingOrFallingBack() {
        for (HttpStatus status : new HttpStatus[]{HttpStatus.SERVICE_UNAVAILABLE,HttpStatus.CONFLICT}) {
            AtomicInteger calls = new AtomicInteger();
            var web = WebClient.builder().exchangeFunction(r -> { calls.incrementAndGet(); return Mono.just(response(status,"{}")); }).build();
            var error = assertThrows(ActionWorkflowClient.GatewayException.class,
                    () -> new ActionWorkflowClient(web,props).invoke(snapshot,"recover",null,null));
            assertEquals(status.value(),error.status()); assertEquals(status.is5xxServerError(),error.recoverable());
            assertEquals(1,calls.get());
        }
    }
    @Test void incompleteOrContradictoryReceiptsCannotAdvertiseBusinessSuccess() {
        for (String json : new String[]{
                "{\"actionId\":\"act\",\"workflowStatus\":\"COMPLETED\",\"nativeInterrupt\":true,\"result\":{}}",
                "{\"actionId\":\"act\",\"workflowStatus\":\"EXECUTING\",\"nativeInterrupt\":true,\"result\":{\"type\":\"ORDER_CREATE\",\"actionStatus\":\"CONFIRMED\"}}",
                "{\"actionId\":\"act\",\"workflowStatus\":\"COMPLETED\",\"nativeInterrupt\":true,\"result\":{\"type\":\"ORDER_CANCEL\",\"actionStatus\":\"CONFIRMED\"}}"}) {
            var web = WebClient.builder().exchangeFunction(r -> Mono.just(response(HttpStatus.OK,json))).build();
            assertThrows(ActionWorkflowClient.GatewayException.class,
                    () -> new ActionWorkflowClient(web,props).invoke(snapshot,"recover",null,null));
        }
    }

    @Test void transportAndInvalidReceiptsAreRecoverableNotFalseSuccess() {
        for (String body : new String[]{"{}", "{\"actionId\":\"other\",\"workflowStatus\":\"COMPLETED\",\"nativeInterrupt\":true}",
                "{\"actionId\":\"act\",\"workflowStatus\":\"COMPLETED\",\"nativeInterrupt\":true}"}) {
            var web = WebClient.builder().exchangeFunction(r -> Mono.just(response(HttpStatus.OK,body))).build();
            assertTrue(assertThrows(ActionWorkflowClient.GatewayException.class,
                    () -> new ActionWorkflowClient(web,props).invoke(snapshot,"recover",null,null)).recoverable());
        }
        var web = WebClient.builder().exchangeFunction(r -> Mono.error(new IllegalStateException("unavailable"))).build();
        assertTrue(assertThrows(ActionWorkflowClient.GatewayException.class,
                () -> new ActionWorkflowClient(web,props).invoke(snapshot,"recover",null,null)).recoverable());
    }
    @Test void classifiesFailuresWithoutReplayingAuthBusinessOrTransientResponses() {
        for (int status : new int[]{401,403,409,422,408,429,500,501,502,503,504}) {
            AtomicInteger calls = new AtomicInteger();
            var web = WebClient.builder().exchangeFunction(r -> {
                calls.incrementAndGet(); return Mono.just(response(HttpStatus.valueOf(status),"{}"));
            }).build();
            var error = assertThrows(ActionWorkflowClient.GatewayException.class,
                    () -> new ActionWorkflowClient(web,props).invoke(snapshot,"resume","approve",null));
            var expected = status==401 || status==403 ? ActionWorkflowClient.FailureKind.AUTHORIZATION
                    : java.util.Set.of(408,429,500,502,503,504).contains(status)
                    ? ActionWorkflowClient.FailureKind.TRANSIENT_HTTP : ActionWorkflowClient.FailureKind.PERMANENT_HTTP;
            assertEquals(expected,error.failureKind()); assertEquals(1,calls.get());
            assertEquals(expected==ActionWorkflowClient.FailureKind.TRANSIENT_HTTP,error.recoverable());
        }
    }

    @Test void tlsProtocolAndInvalidJsonAreNotTransientFailuresAndNeverReplay() {
        for (Throwable failure : new Throwable[]{new javax.net.ssl.SSLException("certificate rejected"),
                new java.net.ProtocolException("invalid protocol"),new java.net.ConnectException("connection lost")}) {
            AtomicInteger calls = new AtomicInteger();
            var web = WebClient.builder().exchangeFunction(r -> { calls.incrementAndGet(); return Mono.error(failure); }).build();
            var error = assertThrows(ActionWorkflowClient.GatewayException.class,
                    () -> new ActionWorkflowClient(web,props).invoke(snapshot,"resume","approve",null));
            assertEquals(failure instanceof java.net.ConnectException ? ActionWorkflowClient.FailureKind.TRANSPORT
                    : ActionWorkflowClient.FailureKind.PERMANENT_CLIENT,error.failureKind());
            assertEquals(1,calls.get());
        }
        AtomicInteger calls = new AtomicInteger();
        var web = WebClient.builder().exchangeFunction(r -> {
            calls.incrementAndGet(); return Mono.just(response(HttpStatus.OK,"{broken json"));
        }).build();
        var error = assertThrows(ActionWorkflowClient.GatewayException.class,
                () -> new ActionWorkflowClient(web,props).invoke(snapshot,"recover",null,null));
        assertEquals(ActionWorkflowClient.FailureKind.INVALID_RESPONSE,error.failureKind());
        assertEquals(1,calls.get());
    }
}
