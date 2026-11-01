package com.aimall.backend.common;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.*;

class RequestBudgetTest {
    @Test void nestingOnlyTightensDeadlineAndPermitsAndRestoresScopeAfterFailure() {
        var time = new AtomicLong();
        try (var outer = RequestBudget.open(Duration.ofSeconds(30),2,time::get)) {
            time.addAndGet(Duration.ofSeconds(5).toNanos());
            assertThrows(IllegalStateException.class, () -> {
                try (var inner = RequestBudget.open(Duration.ofMinutes(1),99)) {
                    assertSame(inner,RequestBudget.current());
                    var headers = new HttpHeaders(); inner.writeHeaders(headers);
                    assertEquals("24975",headers.getFirst(RequestBudget.TIMEOUT_HEADER));
                    assertEquals("2",headers.getFirst(RequestBudget.RETRY_HEADER));
                    time.addAndGet(Duration.ofSeconds(25).toNanos());
                    assertThrows(RequestBudget.DeadlineExceeded.class,inner::remainingTimeout);
                    throw new IllegalStateException("operation failed");
                }
            });
            assertSame(outer,RequestBudget.current());
            assertThrows(RequestBudget.DeadlineExceeded.class,outer::remainingTimeout);
        }
        assertNull(RequestBudget.current());
    }

    @Test void asyncCaptureDoesNotInstallThreadLocalOrRefreshBudgetAfterScopeCloses() {
        var time = new AtomicLong(); RequestBudget captured;
        try (var ignored = RequestBudget.open(Duration.ofSeconds(30),0,time::get)) {
            captured = RequestBudget.forOperation(Duration.ofMinutes(3));
            assertNotSame(captured,RequestBudget.current());
        }
        assertNull(RequestBudget.current());
        time.addAndGet(Duration.ofSeconds(7).toNanos());
        var headers = new HttpHeaders(); captured.writeHeaders(headers);
        assertEquals("22975",headers.getFirst(RequestBudget.TIMEOUT_HEADER));
        assertEquals("0",headers.getFirst(RequestBudget.RETRY_HEADER));
        time.addAndGet(Duration.ofSeconds(23).toNanos());
        assertThrows(RequestBudget.DeadlineExceeded.class,captured::remainingTimeout);
    }

    @Test void configuredTimeoutHasAHardCeilingAndNearExpiryCannotDispatch() {
        var time = new AtomicLong();
        try (var scope = RequestBudget.open(Duration.ofDays(1),99,time::get)) {
            var headers = new HttpHeaders(); scope.writeHeaders(headers);
            assertEquals("599975",headers.getFirst(RequestBudget.TIMEOUT_HEADER));
            assertEquals("6",headers.getFirst(RequestBudget.RETRY_HEADER));
            time.addAndGet(Duration.ofMillis(599975).toNanos());
            assertThrows(RequestBudget.DeadlineExceeded.class,() -> scope.writeHeaders(new HttpHeaders()));
        }
        assertNull(RequestBudget.current());
    }
}
