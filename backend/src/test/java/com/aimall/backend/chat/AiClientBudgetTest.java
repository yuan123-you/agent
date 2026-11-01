package com.aimall.backend.chat;

import com.aimall.backend.config.AppProperties;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.reactive.function.client.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

/** Fault injection is in-memory: no sockets or paid services. */
class AiClientBudgetTest {
    private final AppProperties props = new AppProperties();
    private Throwable root(Throwable error) {
        while (error.getCause()!=null) error=error.getCause(); return error;
    }
    private ClientResponse stream(Flux<String> events) {
        return ClientResponse.create(HttpStatus.OK).header("Content-Type","text/event-stream")
                .body(events.map(s -> new org.springframework.core.io.buffer.DefaultDataBufferFactory()
                        .wrap(s.getBytes(java.nio.charset.StandardCharsets.UTF_8)))).build();
    }
    @Test void chatDeadlineIsTotalDespiteContinuousEventsAndCancellationDoesNotReplay() throws Exception {
        props.getAi().setChatTimeout(Duration.ofMillis(600));
        var calls = new AtomicInteger(); var received = new AtomicInteger(); var cancelled = new java.util.concurrent.CountDownLatch(1);
        var web = WebClient.builder().exchangeFunction(request -> {
            calls.incrementAndGet();
            return Mono.just(stream(Flux.interval(Duration.ofMillis(20))
                    .map(n -> "event: token\ndata: {\"text\":\"partial\"}\n\n")
                    .doOnCancel(cancelled::countDown)));
        }).build();
        var error = assertThrows(RuntimeException.class, () -> new AiClient(web,props).streamChat(Map.of())
                .doOnNext(event -> received.incrementAndGet()).blockLast(Duration.ofSeconds(3)));
        assertInstanceOf(TimeoutException.class,root(error));
        assertTrue(root(error).getMessage().contains("total deadline"),"must expire upstream, not the test's blocking guard");
        assertTrue(received.get()>0,"partial stream must have started before deadline");
        assertEquals(1,calls.get()); assertTrue(cancelled.await(1,java.util.concurrent.TimeUnit.SECONDS));
    }
    @Test void partialStreamTransportFailureAndHttpAuthBusinessTransientFailuresNeverReplay() {
        var calls = new AtomicInteger(); var received = new AtomicInteger();
        var web = WebClient.builder().exchangeFunction(request -> {
            calls.incrementAndGet();
            return Mono.just(stream(Flux.concat(Flux.just("event: token\ndata: partial\n\n"),
                    Flux.error(new IllegalStateException("connection lost after token")))));
        }).build();
        assertThrows(RuntimeException.class,() -> new AiClient(web,props).streamChat(Map.of())
                .doOnNext(event -> received.incrementAndGet()).blockLast());
        assertEquals(1,calls.get()); assertEquals(1,received.get());
        for (HttpStatus status : new HttpStatus[]{HttpStatus.UNAUTHORIZED,HttpStatus.FORBIDDEN,HttpStatus.CONFLICT,
                HttpStatus.UNPROCESSABLE_ENTITY,HttpStatus.SERVICE_UNAVAILABLE,HttpStatus.TOO_MANY_REQUESTS}) {
            calls.set(0);
            var failing = WebClient.builder().exchangeFunction(request -> {
                calls.incrementAndGet(); return Mono.just(ClientResponse.create(status).body("{}").build());
            }).build();
            var error = assertThrows(WebClientResponseException.class,
                    () -> new AiClient(failing,props).streamChat(Map.of()).blockLast());
            assertEquals(status,error.getStatusCode()); assertEquals(1,calls.get());
        }
    }
    @Test void chatAndUnsafeIngestSendLocallyBoundedHeadersAndIngestIsSingleAttempt() {
        var sent = new AtomicReference<ClientRequest>(); var calls = new AtomicInteger();
        var web = WebClient.builder().exchangeFunction(request -> {
            sent.set(request); calls.incrementAndGet();
            return Mono.just(ClientResponse.create(HttpStatus.SERVICE_UNAVAILABLE).body("{}").build());
        }).build();
        var client = new AiClient(web,props);
        assertThrows(WebClientResponseException.class, () -> client.streamChat(Map.of()).blockLast());
        long timeout = Long.parseLong(sent.get().headers().getFirst("X-Request-Timeout-Ms"));
        assertTrue(timeout>170000 && timeout<180000);
        assertEquals("6",sent.get().headers().getFirst("X-Request-Retry-Budget"));
        calls.set(0);
        assertThrows(WebClientResponseException.class, () -> client.triggerIngest(Map.of("task_id","unsafe-write")).block());
        assertEquals(1,calls.get());
        assertTrue(Long.parseLong(sent.get().headers().getFirst("X-Request-Timeout-Ms"))<30000);
    }
    @Test void ingestTransportTimeoutIsBoundedAndNeverRetried() {
        props.getAi().setIngestTimeout(Duration.ofMillis(80));
        var calls = new AtomicInteger();
        var web = WebClient.builder().exchangeFunction(request -> { calls.incrementAndGet(); return Mono.never(); }).build();
        var error = assertThrows(RuntimeException.class,
                () -> new AiClient(web,props).triggerIngest(Map.of()).block(Duration.ofSeconds(2)));
        assertInstanceOf(TimeoutException.class,root(error));
        assertFalse(root(error).getMessage().contains("blocking read"),"must expire upstream, not the test's blocking guard");
        assertEquals(1,calls.get());
    }
    @Test void auxiliaryCallsCaptureBudgetBeforeAsyncSubscriptionAndKeepGracefulDegradation() {
        var sent = new AtomicReference<ClientRequest>(); var calls = new AtomicInteger();
        var web = WebClient.builder().baseUrl("http://not-used.invalid").exchangeFunction(request -> {
            sent.set(request); calls.incrementAndGet(); return Mono.never();
        }).build();
        var client = new AiClient(web,props);
        Mono<String> summary;
        try (var ignored = com.aimall.backend.common.RequestBudget.open(Duration.ofMillis(150),1)) {
            summary = client.summarize(Map.of());
        }
        assertEquals("",summary.block(Duration.ofSeconds(2)));
        assertEquals(1,calls.get());
        assertEquals("1",sent.get().headers().getFirst("X-Request-Retry-Budget"));
        assertTrue(Long.parseLong(sent.get().headers().getFirst("X-Request-Timeout-Ms"))<150);
        Mono<Void> deletion;
        try (var ignored = com.aimall.backend.common.RequestBudget.open(Duration.ofMillis(150),0)) {
            deletion = client.deleteVectors(10L,1);
        }
        deletion.block(Duration.ofSeconds(2));
        assertEquals(2,calls.get());
        assertEquals("0",sent.get().headers().getFirst("X-Request-Retry-Budget"));
        assertTrue(Long.parseLong(sent.get().headers().getFirst("X-Request-Timeout-Ms"))<150);
    }
}
