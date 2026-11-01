package com.aimall.backend.common;

import org.springframework.http.HttpHeaders;

import java.time.Duration;
import java.util.function.LongSupplier;

/**
 * Monotonic operation deadline, not a retry loop or a distributed permit ledger.
 * Scopes are synchronous (servlet callback/native coordinator); async clients capture an immutable budget.
 */
public final class RequestBudget implements AutoCloseable {
    public static final String TIMEOUT_HEADER = "X-Request-Timeout-Ms";
    public static final String RETRY_HEADER = "X-Request-Retry-Budget";
    public static final int MAX_RETRY_BUDGET = 6;
    private static final Duration MAX_TIMEOUT = Duration.ofMinutes(10);
    private static final long DISPATCH_RESERVE_NANOS = Duration.ofMillis(25).toNanos();
    private static final ThreadLocal<RequestBudget> CURRENT = new ThreadLocal<>();

    private final long deadline;
    private final LongSupplier ticker;
    private final int retryBudget;
    private final RequestBudget parent;
    private final boolean scoped;

    private RequestBudget(Duration timeout, int retryBudget, LongSupplier ticker, boolean scoped) {
        if (timeout.isNegative()) throw new IllegalArgumentException("Negative operation timeout");
        this.parent = CURRENT.get();
        this.ticker = parent == null ? ticker : parent.ticker;
        long remaining = timeout.compareTo(MAX_TIMEOUT)>0 ? MAX_TIMEOUT.toNanos() : timeout.toNanos();
        long now = this.ticker.getAsLong();
        if (parent != null) remaining = Math.min(remaining, parent.deadline-now);
        this.deadline = now+remaining;
        int permits = Math.max(0, Math.min(MAX_RETRY_BUDGET,retryBudget));
        this.retryBudget = parent == null ? permits : Math.min(permits,parent.retryBudget);
        this.scoped = scoped;
        if (scoped) CURRENT.set(this);
    }

    public static RequestBudget current() { return CURRENT.get(); }

    public static RequestBudget open(Duration timeout,int retryBudget) {
        return open(timeout,retryBudget,System::nanoTime);
    }

    // Injectable monotonic source keeps deadline arithmetic verifiable without wall-clock sleeps.
    static RequestBudget open(Duration timeout,int retryBudget,LongSupplier ticker) {
        return new RequestBudget(timeout,retryBudget,ticker,true);
    }

    public static RequestBudget forOperation(Duration timeout) {
        return new RequestBudget(timeout,MAX_RETRY_BUDGET,System::nanoTime,false);
    }

    /** Leave room for header construction/dispatch; floor milliseconds, never round a deadline up. */
    public Duration remainingTimeout() {
        long millis = (deadline-ticker.getAsLong()-DISPATCH_RESERVE_NANOS)/1_000_000;
        if (millis<=0) throw new DeadlineExceeded();
        return Duration.ofMillis(millis);
    }

    public void writeHeaders(HttpHeaders headers) {
        headers.set(TIMEOUT_HEADER,Long.toString(remainingTimeout().toMillis()));
        headers.set(RETRY_HEADER,Integer.toString(retryBudget));
    }

    /** Only call after internal-token validation. Invalid input cannot raise the local limit. */
    public static Duration trustedTimeout(String value,Duration localLimit) {
        try {
            long millis = Long.parseLong(value);
            if (millis>=0) return Duration.ofMillis(Math.min(millis,localLimit.toMillis()));
        } catch (NumberFormatException ignored) { }
        return localLimit;
    }

    public static int trustedRetryBudget(String value) {
        try {
            long permits = Long.parseLong(value);
            if (permits>=0) return (int)Math.min(permits,MAX_RETRY_BUDGET);
        } catch (NumberFormatException ignored) { }
        return MAX_RETRY_BUDGET;
    }

    @Override public void close() {
        if (scoped) {
            if (parent==null) CURRENT.remove(); else CURRENT.set(parent);
        }
    }

    public static final class DeadlineExceeded extends RuntimeException {
        public DeadlineExceeded() { super("Operation deadline exhausted before dispatch"); }
    }
}
