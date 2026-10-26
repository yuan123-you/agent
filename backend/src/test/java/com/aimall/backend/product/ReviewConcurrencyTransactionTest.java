package com.aimall.backend.product;

import com.aimall.backend.common.BizException;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import static org.junit.jupiter.api.Assertions.*;

class ReviewConcurrencyTransactionTest {
    private ReviewControllerTest.SqlFixture db;
    @BeforeEach void setUp() { db = new ReviewControllerTest.SqlFixture(); }
    @AfterEach void tearDown() { db.close(); }

    @Test void userLockIsFirstSqlAndEveryCreateQueryRunsInsideTransaction() throws Exception {
        db.controller.create(7L, 1L, ReviewControllerTest.body(40L));
        String first = db.trace.queries.get(0).toLowerCase(java.util.Locale.ROOT);
        assertTrue(first.contains("sys_user") && first.contains("for update"),
                "locking read must precede product/duplicate/purchase reads, so no RR snapshot predates the user lock: " + first);
        assertTrue(db.trace.transactional.stream().allMatch(Boolean::booleanValue), "lock must survive until insert commits");
    }

    @Test void racingReviewsOnDifferentOrdersSerializeAndOnlyOneActiveReviewCommits() throws Exception {
        var firstRead = new CountDownLatch(1);
        var releaseFirstRead = new CountDownLatch(1);
        var secondAtSql = new CountDownLatch(1);
        var paused = new AtomicBoolean();
        db.trace.afterQuery = statement -> {
            if (statement.endsWith(".selectCount") && paused.compareAndSet(false, true)) {
                firstRead.countDown();
                await(releaseFirstRead);
            }
        };
        db.trace.beforeQuery = () -> {
            if (Thread.currentThread().getName().equals("second-review")) secondAtSql.countDown();
        };
        var firstBody = ReviewControllerTest.body(40L);
        var secondBody = ReviewControllerTest.body(44L);
        var pool = Executors.newFixedThreadPool(2);
        Future<Boolean> first = null;
        Future<Boolean> second = null;
        boolean secondBlocked;
        try {
            first = pool.submit(() -> create(firstBody));
            assertTrue(firstRead.await(5, TimeUnit.SECONDS), "first transaction must reach the duplicate check");
            second = pool.submit(() -> {
                Thread.currentThread().setName("second-review");
                return create(secondBody);
            });
            assertTrue(secondAtSql.await(5, TimeUnit.SECONDS), "second request must enter the SQL layer");
            try { second.get(350, TimeUnit.MILLISECONDS); secondBlocked = false; }
            catch (TimeoutException expected) { secondBlocked = true; }
            releaseFirstRead.countDown();
            int successes = (first.get(10, TimeUnit.SECONDS) ? 1 : 0) + (second.get(10, TimeUnit.SECONDS) ? 1 : 0);
            assertEquals(1, successes, "a second delivered order must not permit a second review for the same product");
            assertEquals(1, db.jdbc.queryForObject("select count(*) from product_review where user_id=7 and product_id=1 and deleted=0", Integer.class));
            assertTrue(secondBlocked, "the second request must wait for the real user-row transaction lock");
        } finally {
            releaseFirstRead.countDown();
            pool.shutdown();
            if (!pool.awaitTermination(15, TimeUnit.SECONDS)) pool.shutdownNow();
        }
    }

    @Test void reviewInsertRollsBackWithEnclosingTransaction() throws Exception {
        var body = ReviewControllerTest.body(40L);
        var tx = new TransactionTemplate(db.context.getBean(PlatformTransactionManager.class));
        assertThrows(IllegalStateException.class, () -> tx.executeWithoutResult(status -> {
            db.controller.create(7L, 1L, body);
            throw new IllegalStateException("rollback review");
        }));
        assertEquals(0, db.jdbc.queryForObject("select count(*) from product_review", Integer.class));
    }

    @Test void databaseInsertFailureIsNotReportedAsSuccess() throws Exception {
        db.jdbc.execute("alter table product_review add constraint reject_review check(rating < 4)");
        var body = ReviewControllerTest.body(40L);
        assertThrows(RuntimeException.class, () -> db.controller.create(7L, 1L, body));
        assertEquals(0, db.jdbc.queryForObject("select count(*) from product_review", Integer.class));
    }

    private boolean create(ReviewController.CreateBody body) {
        try { db.controller.create(7L, 1L, body); return true; }
        catch (BizException e) { assertEquals(2004, e.getCode()); return false; }
    }

    private static void await(CountDownLatch latch) {
        try { if (!latch.await(10, TimeUnit.SECONDS)) throw new AssertionError("race gate timed out"); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new AssertionError(e); }
    }
}
