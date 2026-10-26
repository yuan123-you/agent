package com.aimall.backend.promotion;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.*;
import com.aimall.backend.mapper.*;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.extension.spring.MybatisSqlSessionFactoryBean;
import org.apache.ibatis.session.SqlSessionFactory;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mybatis.spring.mapper.MapperFactoryBean;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import javax.sql.DataSource;
import java.math.BigDecimal;
import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class PromotionReceiveTransactionTest {
    static class Gate {
        volatile CountDownLatch snapshot, release, couponSnapshot, couponRelease;
        volatile int restockFailures;
        final java.util.concurrent.atomic.AtomicBoolean firstCoupon = new java.util.concurrent.atomic.AtomicBoolean(true);
        final java.util.concurrent.atomic.AtomicBoolean first = new java.util.concurrent.atomic.AtomicBoolean(true);
    }
    @Configuration
    @EnableTransactionManagement(proxyTargetClass = true)
    static class Config {
        @Bean DataSource dataSource() { return new DriverManagerDataSource("jdbc:h2:mem:coupon_" + UUID.randomUUID()
                + ";MODE=MySQL;DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=10000", "sa", ""); }
        @Bean JdbcTemplate jdbc(DataSource ds) { return new JdbcTemplate(ds); }
        @Bean PlatformTransactionManager transactionManager(DataSource ds) { return new DataSourceTransactionManager(ds); }
        @Bean SqlSessionFactory factory(DataSource ds) throws Exception {
            var bean = new MybatisSqlSessionFactoryBean(); bean.setDataSource(ds);
            var config = new MybatisConfiguration(); config.setMapUnderscoreToCamelCase(true); bean.setConfiguration(config);
            var plugin=new com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor();
            plugin.addInnerInterceptor(new com.baomidou.mybatisplus.extension.plugins.inner.OptimisticLockerInnerInterceptor());
            bean.setPlugins(plugin);
            return bean.getObject();
        }
        @Bean MapperFactoryBean<MallCouponMapper> coupons(SqlSessionFactory f) {
            var bean = new MapperFactoryBean<>(MallCouponMapper.class); bean.setSqlSessionFactory(f); return bean;
        }
        @Bean MapperFactoryBean<UserCouponMapper> userCoupons(SqlSessionFactory f) {
            var bean = new MapperFactoryBean<>(UserCouponMapper.class); bean.setSqlSessionFactory(f); return bean;
        }
        @Bean MapperFactoryBean<MallSeckillMapper> seckills(SqlSessionFactory f) {
            var bean = new MapperFactoryBean<>(MallSeckillMapper.class); bean.setSqlSessionFactory(f); return bean;
        }
        @Bean Gate gate() { return new Gate(); }
        @Bean PromotionService service(MallCouponMapper mapper, UserCouponMapper users, MallSeckillMapper seckills, Gate gate) {
            MallCouponMapper observed = (MallCouponMapper) Proxy.newProxyInstance(MallCouponMapper.class.getClassLoader(),
                new Class<?>[]{MallCouponMapper.class}, (proxy,method,args) -> {
                    Object result;
                    try { result=method.invoke(mapper,args); } catch (InvocationTargetException e) { throw e.getCause(); }
                    if (method.getName().equals("selectById") && gate.snapshot != null && gate.first.compareAndSet(true,false)) {
                        gate.snapshot.countDown();
                        if (!gate.release.await(5,TimeUnit.SECONDS)) throw new AssertionError("coupon snapshot timeout");
                    }
                    return result;
                });
            UserCouponMapper observedUsers = (UserCouponMapper) Proxy.newProxyInstance(UserCouponMapper.class.getClassLoader(),
                new Class<?>[]{UserCouponMapper.class}, (proxy,method,args) -> {
                    Object result;
                    try { result=method.invoke(users,args); } catch (InvocationTargetException e) { throw e.getCause(); }
                    if (method.getName().equals("selectById") && gate.couponSnapshot != null && gate.firstCoupon.compareAndSet(true,false)) {
                        gate.couponSnapshot.countDown();
                        if (!gate.couponRelease.await(5,TimeUnit.SECONDS)) throw new AssertionError("release snapshot timeout");
                    }
                    return result;
                });
            MallSeckillMapper observedSeckills = (MallSeckillMapper) Proxy.newProxyInstance(MallSeckillMapper.class.getClassLoader(),
                new Class<?>[]{MallSeckillMapper.class}, (proxy,method,args) -> {
                    if (method.getName().equals("updateById") && gate.restockFailures > 0) { gate.restockFailures--; return 0; }
                    try { return method.invoke(seckills,args); } catch (InvocationTargetException e) { throw e.getCause(); }
                });
            return new PromotionService(observed,observedUsers,observedSeckills,mock(ProductMapper.class));
        }
    }
    private AnnotationConfigApplicationContext context;
    private JdbcTemplate jdbc;
    private PromotionService service;
    private Gate gate;
    @BeforeEach void setup() {
        context=new AnnotationConfigApplicationContext(Config.class); jdbc=context.getBean(JdbcTemplate.class);
        service=context.getBean(PromotionService.class); gate=context.getBean(Gate.class);
        table("mall_coupon",MallCoupon.class); table("user_coupon",UserCoupon.class); table("mall_seckill",MallSeckill.class);
        jdbc.update("insert into mall_seckill(id,product_id,seckill_stock,version,deleted) values(11,1,3,0,0)");
        jdbc.execute("alter table user_coupon add unique(coupon_id,user_id)");
        jdbc.update("insert into mall_coupon(id,name,discount_value,min_amount,total_count,received_count,per_limit,status,valid_days,deleted) "
                + "values(1,'Coupon',10,0,3,0,1,'ENABLE',7,0)");
    }
    private void table(String name, Class<?> entity) {
        var columns = new ArrayList<String>();
        for (var field : entity.getDeclaredFields()) {
            if (java.lang.reflect.Modifier.isStatic(field.getModifiers())) continue;
            String column = field.getName().replaceAll("([a-z0-9])([A-Z])", "$1_$2").toLowerCase(Locale.ROOT);
            Class<?> t = field.getType();
            String type = t == Long.class ? "bigint" : t == Integer.class ? "integer" : t == BigDecimal.class ? "decimal(18,2)"
                    : t == java.time.LocalDateTime.class ? "timestamp" : "varchar(4096)";
            columns.add(column + (column.equals("id") ? " bigint generated by default as identity primary key" : " " + type)
                    + (column.equals("deleted") ? " default 0" : ""));
        }
        jdbc.execute("create table " + name + "(" + String.join(",", columns) + ")");
    }
    @AfterEach void close() { jdbc.execute("drop all objects"); context.close(); }
    private int received() { return jdbc.queryForObject("select received_count from mall_coupon where id=1",Integer.class); }
    private int holdings() { return jdbc.queryForObject("select count(*) from user_coupon",Integer.class); }
    @ParameterizedTest
    @ValueSource(strings={"DISABLE","EXPIRED","NOT_STARTED"})
    void eligibilityChangesBeforeAtomicClaimAreRespected(String change) throws Exception {
        gate.snapshot=new CountDownLatch(1); gate.release=new CountDownLatch(1);
        var pool=Executors.newSingleThreadExecutor();
        try {
            var claim=pool.submit(() -> {
                try { service.receive(7L,1L); return true; } catch (BizException rejected) { return false; }
            });
            assertTrue(gate.snapshot.await(5,TimeUnit.SECONDS));
            var update=new PromotionService.CouponSaveRequest();
            if (change.equals("DISABLE")) update.setStatus("DISABLE");
            if (change.equals("EXPIRED")) update.setEndTime(java.time.LocalDateTime.now().minusDays(1));
            if (change.equals("NOT_STARTED")) update.setStartTime(java.time.LocalDateTime.now().plusDays(1));
            service.updateCoupon(1L,update);
            gate.release.countDown();
            assertFalse(claim.get(10,TimeUnit.SECONDS),"stale eligibility must not grant a coupon");
            assertEquals(0,received()); assertEquals(0,holdings());
        } finally { gate.release.countDown(); pool.shutdownNow(); }
    }
    @Test void concurrentDistinctUsersCannotExceedTotalCount() throws Exception {
        var pool=Executors.newFixedThreadPool(8); var start=new CyclicBarrier(8);
        try {
            var futures=new ArrayList<Future<Boolean>>();
            for (long user=1;user<=8;user++) {
                final long id=user;
                futures.add(pool.submit(() -> {
                    start.await(); try { service.receive(id,1L); return true; }
                    catch (BizException rejected) { assertEquals(2204,rejected.getCode()); return false; }
                }));
            }
            int winners=0; for (var result:futures) if (result.get(15,TimeUnit.SECONDS)) winners++;
            assertEquals(3,winners); assertEquals(3,received()); assertEquals(3,holdings());
        } finally { pool.shutdownNow(); }
    }
    @Test void concurrentDuplicateUserClaimsRollbackLosingCounters() throws Exception {
        jdbc.update("update mall_coupon set total_count=20");
        var pool=Executors.newFixedThreadPool(4); var start=new CyclicBarrier(4);
        try {
            var futures=new ArrayList<Future<Boolean>>();
            for (int i=0;i<4;i++) futures.add(pool.submit(() -> {
                start.await(); try { service.receive(7L,1L); return true; }
                catch (BizException rejected) { assertEquals(2205,rejected.getCode()); return false; }
            }));
            int winners=0; for (var result:futures) if (result.get(15,TimeUnit.SECONDS)) winners++;
            assertEquals(1,winners); assertEquals(1,received()); assertEquals(1,holdings());
            assertEquals(2205,assertThrows(BizException.class,() -> service.receive(7L,1L)).getCode());
            assertEquals(1,received());
        } finally { pool.shutdownNow(); }
    }
    @Test void reducingTotalBelowReceivedCountMustNotInvalidateIssuedCoupons() {
        service.receive(7L,1L); service.receive(8L,1L);
        var update=new PromotionService.CouponSaveRequest(); update.setTotalCount(1);
        assertEquals(2001,assertThrows(BizException.class,() -> service.updateCoupon(1L,update)).getCode());
        assertEquals(3,jdbc.queryForObject("select total_count from mall_coupon where id=1",Integer.class));
        assertEquals(2,received()); assertEquals(2,holdings());
    }
    @Test void concurrentClaimPreventsReductionBelowNewReceivedCount() throws Exception {
        service.receive(7L,1L); gate.snapshot=new CountDownLatch(1); gate.release=new CountDownLatch(1);
        var pool=Executors.newSingleThreadExecutor();
        try {
            var reduction=pool.submit(() -> {
                var update=new PromotionService.CouponSaveRequest(); update.setTotalCount(1);
                try { service.updateCoupon(1L,update); return true; } catch (BizException rejected) { return false; }
            });
            assertTrue(gate.snapshot.await(5,TimeUnit.SECONDS));
            service.receive(8L,1L); gate.release.countDown();
            assertFalse(reduction.get(10,TimeUnit.SECONDS)); assertEquals(2,received()); assertEquals(2,holdings());
            assertEquals(3,jdbc.queryForObject("select total_count from mall_coupon where id=1",Integer.class));
        } finally { gate.release.countDown(); pool.shutdownNow(); }
    }

    @ParameterizedTest @ValueSource(ints={0,-1})
    void nonPositiveIssuanceTotalIsRejected(int total) {
        var update=new PromotionService.CouponSaveRequest(); update.setTotalCount(total);
        assertEquals(2001,assertThrows(BizException.class,() -> service.updateCoupon(1L,update)).getCode());
        assertEquals(3,jdbc.queryForObject("select total_count from mall_coupon where id=1",Integer.class));
    }

    @Test void exhaustedRestockRetriesMustRollbackCallerTransaction() {
        gate.restockFailures=5;
        var tx=new org.springframework.transaction.support.TransactionTemplate(context.getBean(PlatformTransactionManager.class));
        assertEquals(2206,assertThrows(BizException.class,() -> tx.executeWithoutResult(status -> {
            jdbc.update("update mall_coupon set received_count=1 where id=1");
            service.restockSeckill(11L,2);
        })).getCode());
        assertEquals(0,received());
        assertEquals(3,jdbc.queryForObject("select seckill_stock from mall_seckill where id=11",Integer.class));
        assertEquals(0,gate.restockFailures);
    }
    @Test void transientRestockConflictsRetryAndRestoreExactlyOnce() {
        gate.restockFailures=2; service.restockSeckill(11L,2);
        assertEquals(5,jdbc.queryForObject("select seckill_stock from mall_seckill where id=11",Integer.class));
        assertEquals(1,jdbc.queryForObject("select version from mall_seckill where id=11",Integer.class));
    }
    @Test void releaseReallyClearsPreviousOrderAndTimestampAndCanBeReused() {
        long id=service.receive(7L,1L); service.markCouponUsed(7L,id,100L);
        var tx=new org.springframework.transaction.support.TransactionTemplate(context.getBean(PlatformTransactionManager.class));
        tx.executeWithoutResult(status -> service.releaseCoupon(id));
        var row=jdbc.queryForMap("select status,used_order_id,used_at from user_coupon where id=?",id);
        assertEquals("UNUSED",row.get("status")); assertNull(row.get("used_order_id")); assertNull(row.get("used_at"));
        service.releaseCoupon(id); // Preserve the existing already-released no-op contract.
        service.markCouponUsed(7L,id,200L);
        assertEquals(200L,jdbc.queryForObject("select used_order_id from user_coupon where id=?",Long.class,id));
    }
    @Test void staleReleaseCannotReleaseCouponReusedByAnotherOrderAndRollsBackCaller() throws Exception {
        long id=service.receive(7L,1L); service.markCouponUsed(7L,id,100L);
        gate.couponSnapshot=new CountDownLatch(1); gate.couponRelease=new CountDownLatch(1);
        var tx=new org.springframework.transaction.support.TransactionTemplate(context.getBean(PlatformTransactionManager.class));
        var pool=Executors.newSingleThreadExecutor();
        try {
            var release=pool.submit(() -> {
                try {
                    tx.executeWithoutResult(status -> {
                        jdbc.update("update mall_coupon set status='DISABLE' where id=1");
                        service.releaseCoupon(id);
                    });
                    return true;
                } catch (BizException conflict) { assertEquals(2209,conflict.getCode()); return false; }
            });
            assertTrue(gate.couponSnapshot.await(5,TimeUnit.SECONDS));
            service.releaseCoupon(id); service.markCouponUsed(7L,id,200L); gate.couponRelease.countDown();
            assertFalse(release.get(10,TimeUnit.SECONDS));
            var row=jdbc.queryForMap("select status,used_order_id,used_at from user_coupon where id=?",id);
            assertEquals("USED",row.get("status")); assertEquals(200L,row.get("used_order_id")); assertNotNull(row.get("used_at"));
            assertEquals("ENABLE",jdbc.queryForObject("select status from mall_coupon where id=1",String.class));
        } finally { gate.couponRelease.countDown(); pool.shutdownNow(); }
    }

}
