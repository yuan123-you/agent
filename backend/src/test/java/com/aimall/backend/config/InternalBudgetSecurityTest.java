package com.aimall.backend.config;

import com.aimall.backend.common.RequestBudget;
import com.aimall.backend.internal.*;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.*;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.reactive.function.client.*;
import reactor.core.publisher.Mono;

import java.time.Instant;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class InternalBudgetSecurityTest {
    private final AppProperties props = new AppProperties();
    private final AtomicReference<ClientRequest> sent = new AtomicReference<>();
    private final AgentOrderActionService actions = mock(AgentOrderActionService.class);
    private final AgentOrderActionService.ActionSnapshot snapshot = new AgentOrderActionService.ActionSnapshot(
            "act",7L,20L,"ORDER_CREATE","PENDING",Instant.parse("2026-11-01T00:00:00Z"),"hash");

    @AfterEach void cleanup() { SecurityContextHolder.clearContext(); assertNull(RequestBudget.current()); }

    private void start() {
        props.getAi().setActionWorkflowsEnabled(true);
        when(actions.snapshot(7L,"act")).thenReturn(snapshot);
        var web = WebClient.builder().exchangeFunction(request -> {
            sent.set(request);
            return Mono.just(ClientResponse.create(org.springframework.http.HttpStatus.OK)
                    .header("Content-Type","application/json")
                    .body("{\"actionId\":\"act\",\"workflowStatus\":\"WAITING_APPROVAL\",\"nativeInterrupt\":true}").build());
        }).build();
        new ActionWorkflowCoordinator(actions,new ActionWorkflowClient(web,props),props).start(7L,"act");
    }
    private MockHttpServletRequest request(String path,String token,String timeout,String permits) {
        props.getAi().setInternalToken("internal-secret");
        var request = new MockHttpServletRequest("POST",path);
        request.addHeader("X-Internal-Token",token);
        request.addHeader("X-Request-Timeout-Ms",timeout);
        request.addHeader("X-Request-Retry-Budget",permits);
        return request;
    }
    private long timeout() { return Long.parseLong(sent.get().headers().getFirst("X-Request-Timeout-Ms")); }

    @Test void validatedCallbackBudgetClipsNestedNativeStartAndDoesNotLeak() throws Exception {
        var response = new MockHttpServletResponse();
        new InternalAuthFilter(props).doFilter(request("/internal/tools/prepare","internal-secret","15000","2"),response,
                (req,res) -> start());
        assertEquals(200,response.getStatus());
        assertTrue(timeout()>0 && timeout()<15000);
        assertEquals("2",sent.get().headers().getFirst("X-Request-Retry-Budget"));
    }
    @Test void authenticatedOversizedAndMalformedBudgetsCannotExtendLocalLimits() throws Exception {
        for (String value : new String[]{"99999999999999999999999999","-1","garbage","999999999"}) {
            new InternalAuthFilter(props).doFilter(request("/internal/tools/prepare","internal-secret",value,value),
                    new MockHttpServletResponse(), (req,res) -> start());
            assertTrue(timeout()>0 && timeout()<30000);
            assertEquals("6",sent.get().headers().getFirst("X-Request-Retry-Budget"));
        }
    }
    @Test void publicHeadersIncludingInternalTokenCannotAlterBudget() throws Exception {
        for (String timeout : new String[]{"0","1","999999999"}) {
            new InternalAuthFilter(props).doFilter(request("/api/v1/order-actions/act/confirm","internal-secret",timeout,"0"),
                    new MockHttpServletResponse(),(req,res) -> start());
            assertTrue(timeout()>29000 && timeout()<30000);
            assertEquals("6",sent.get().headers().getFirst("X-Request-Retry-Budget"));
        }
    }
    @Test void zeroRetryPermitsRemainZeroAndZeroDeadlineCannotEnterChain() throws Exception {
        new InternalAuthFilter(props).doFilter(request("/internal/tools/prepare","internal-secret","15000","0"),
                new MockHttpServletResponse(),(req,res) -> start());
        assertEquals("0",sent.get().headers().getFirst("X-Request-Retry-Budget"));
        sent.set(null);
        clearInvocations(actions);
        var count = new AtomicInteger(); var response = new MockHttpServletResponse();
        new InternalAuthFilter(props).doFilter(request("/internal/tools/prepare","internal-secret","0","6"),response,
                (req,res) -> { count.incrementAndGet(); start(); });
        assertEquals(503,response.getStatus());
        assertEquals(5002,new com.fasterxml.jackson.databind.ObjectMapper()
                .readTree(response.getContentAsString()).path("code").asInt());
        assertEquals(0,count.get()); assertNull(sent.get()); verifyNoInteractions(actions);
    }
    @Test void badInternalTokenNeverReachesCoordinator() throws Exception {
        var count = new AtomicInteger(); var response = new MockHttpServletResponse();
        var request = spy(request("/internal/tools/prepare","wrong","0","0"));
        doThrow(new AssertionError("budget must not be read before authentication"))
                .when(request).getHeader(RequestBudget.TIMEOUT_HEADER);
        doThrow(new AssertionError("budget must not be read before authentication"))
                .when(request).getHeader(RequestBudget.RETRY_HEADER);
        new InternalAuthFilter(props).doFilter(request,response,(req,res) -> count.incrementAndGet());
        assertEquals(401,response.getStatus()); assertEquals(0,count.get()); assertNull(sent.get());
    }
    @Test void rejectedAdmissionRestoresExistingParentScope() throws Exception {
        var count = new AtomicInteger(); var response = new MockHttpServletResponse();
        try (var parent = RequestBudget.open(java.time.Duration.ofSeconds(30),2)) {
            new InternalAuthFilter(props).doFilter(request("/internal/tools/action-workflows/cancel","internal-secret","1","0"),
                    response,(req,res) -> count.incrementAndGet());
            assertSame(parent,RequestBudget.current());
        }
        assertEquals(503,response.getStatus()); assertEquals(0,count.get());
        assertNull(RequestBudget.current()); verifyNoInteractions(actions);
    }
}
