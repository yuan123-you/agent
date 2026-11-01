package com.aimall.backend.common;

import com.aimall.backend.config.AppProperties;
import com.aimall.backend.internal.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.HttpStatus;
import org.springframework.web.reactive.function.client.*;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/** Real coordinator + gateway; only persistence and HTTP exchange are replaced. No network. */
class RequestBudgetIntegrationTest {
    private final AppProperties props = new AppProperties();
    private final AgentOrderActionService actions = mock(AgentOrderActionService.class);
    private final AgentOrderActionService.ActionSnapshot snapshot = new AgentOrderActionService.ActionSnapshot(
            "act",7L,20L,"ORDER_CREATE","PENDING",Instant.parse("2026-11-01T00:00:00Z"),"hash");

    private ClientResponse waiting() {
        return ClientResponse.create(HttpStatus.OK).header("Content-Type","application/json")
                .body("{\"actionId\":\"act\",\"workflowStatus\":\"WAITING_APPROVAL\",\"nativeInterrupt\":true}").build();
    }
    private ActionWorkflowCoordinator coordinator(ExchangeFunction exchange) {
        props.getAi().setActionWorkflowsEnabled(true);
        when(actions.snapshot(7L,"act")).thenReturn(snapshot);
        return new ActionWorkflowCoordinator(actions,new ActionWorkflowClient(
                WebClient.builder().exchangeFunction(exchange).build(),props),props);
    }

    @ParameterizedTest @ValueSource(strings={"resume","recover"})
    void registrationAndDecisionShareOneDecreasingDeadline(String operation) {
        var time = new AtomicLong();
        var requests = new ArrayList<ClientRequest>();
        var coordinator = coordinator(request -> {
            requests.add(request);
            time.addAndGet(Duration.ofSeconds(5).toNanos());
            return Mono.just(waiting());
        });
        try (var ignored = RequestBudget.open(Duration.ofSeconds(30),99,time::get)) {
            if (operation.equals("resume")) coordinator.confirm(7L,"act",null);
            else coordinator.recover(7L,"act");
        }
        assertEquals(2,requests.size());
        assertTrue(requests.get(0).url().getPath().endsWith("/start"));
        assertTrue(requests.get(1).url().getPath().endsWith("/"+operation));
        long first = Long.parseLong(requests.get(0).headers().getFirst("X-Request-Timeout-Ms"));
        long second = Long.parseLong(requests.get(1).headers().getFirst("X-Request-Timeout-Ms"));
        assertTrue(first < 30_000 && first > 29_000,"reserve header/dispatch overhead");
        assertTrue(second <= first-5_000,"never give resume/recover a fresh 30s");
        assertEquals("6",requests.get(1).headers().getFirst("X-Request-Retry-Budget"));
        verify(actions).markNativeManaged(7L,"act");
        verify(actions,never()).confirm(anyLong(),anyString(),any());
        assertNull(RequestBudget.current());
    }

    @Test void expiredRegistrationMakesZeroDecisionCallsAndNeverFallsBack() {
        var time = new AtomicLong();
        var requests = new ArrayList<ClientRequest>();
        var coordinator = coordinator(request -> {
            requests.add(request);
            time.set(Duration.ofSeconds(31).toNanos());
            return Mono.just(waiting());
        });
        try (var ignored = RequestBudget.open(Duration.ofSeconds(30),2,time::get)) {
            assertThrows(ActionWorkflowClient.GatewayException.class, () -> coordinator.confirm(7L,"act",null));
        }
        assertEquals(1,requests.size());
        assertTrue(requests.get(0).url().getPath().endsWith("/start"));
        verify(actions,never()).confirm(anyLong(),anyString(),any());
        assertNull(RequestBudget.current());
    }

    @Test void deadlineIncludesCanonicalReadsAndNoRequestIsSentAfterExhaustion() {
        var time = new AtomicLong();
        var requests = new ArrayList<ClientRequest>();
        var coordinator = coordinator(request -> { requests.add(request); return Mono.just(waiting()); });
        when(actions.snapshot(7L,"act")).thenAnswer(invocation -> {
            time.set(Duration.ofSeconds(31).toNanos()); return snapshot;
        });
        try (var ignored = RequestBudget.open(Duration.ofSeconds(30),0,time::get)) {
            assertThrows(ActionWorkflowClient.GatewayException.class, () -> coordinator.recover(7L,"act"));
        }
        assertTrue(requests.isEmpty());
    }
    @Test void coordinatorCreatesScopeBeforeCanonicalReadsWithoutAnyInboundBudget() {
        assertNull(RequestBudget.current());
        var scopes = new ArrayList<RequestBudget>();
        var coordinator = coordinator(request -> {
            scopes.add(RequestBudget.current()); return Mono.just(waiting());
        });
        when(actions.snapshot(7L,"act")).thenAnswer(invocation -> {
            assertNotNull(RequestBudget.current(),"operation starts before canonical reads"); return snapshot;
        });
        coordinator.recover(7L,"act");
        assertEquals(2,scopes.size()); assertNotNull(scopes.get(0)); assertSame(scopes.get(0),scopes.get(1));
        assertNull(RequestBudget.current());
    }
    @ParameterizedTest @ValueSource(strings={"resume","recover"})
    void ambiguousDecisionTransportTimeoutIsSingleShotNotARegistrationReplay(String operation) {
        var requests = new ArrayList<ClientRequest>();
        var coordinator = coordinator(request -> {
            requests.add(request);
            return requests.size()==1 ? Mono.just(waiting()) : Mono.never();
        });
        try (var ignored = RequestBudget.open(Duration.ofMillis(600),3)) {
            var error = assertThrows(ActionWorkflowClient.GatewayException.class, () -> {
                if (operation.equals("resume")) coordinator.confirm(7L,"act",null);
                else coordinator.recover(7L,"act");
            });
            assertEquals(ActionWorkflowClient.FailureKind.DEADLINE,error.failureKind());
        }
        assertEquals(2,requests.size());
        assertTrue(requests.get(0).url().getPath().endsWith("/start"));
        assertTrue(requests.get(1).url().getPath().endsWith("/"+operation));
        verify(actions,never()).confirm(anyLong(),anyString(),any());
        assertNull(RequestBudget.current());
    }
}
