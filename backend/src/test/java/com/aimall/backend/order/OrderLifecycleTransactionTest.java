package com.aimall.backend.order;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.config.MybatisPlusConfig;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.OrderItem;
import com.aimall.backend.entity.Product;
import com.aimall.backend.entity.MallSku;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.OrderItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.config.GlobalConfig;
import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.spring.MybatisSqlSessionFactoryBean;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Modifier;
import java.lang.reflect.Proxy;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.TimeUnit;
import javax.sql.DataSource;
import org.apache.ibatis.session.SqlSessionFactory;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mybatis.spring.mapper.MapperFactoryBean;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import org.springframework.transaction.support.TransactionTemplate;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class OrderLifecycleTransactionTest {
    static class RaceGate {
        volatile CyclicBarrier afterRead, afterProductRead;
        final java.util.concurrent.atomic.AtomicInteger productReads = new java.util.concurrent.atomic.AtomicInteger();
    }

    @Configuration
    @EnableTransactionManagement(proxyTargetClass = true)
    @Import(MybatisPlusConfig.class)
    static class Config {
        @Bean Clock clock() { return Clock.systemDefaultZone(); }
        @Bean DataSource dataSource() {
            return new DriverManagerDataSource("jdbc:h2:mem:orders_" + UUID.randomUUID()
                    + ";MODE=MySQL;DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=10000", "sa", "");
        }
        @Bean JdbcTemplate jdbc(DataSource source) { return new JdbcTemplate(source); }
        @Bean PlatformTransactionManager transactionManager(DataSource source) { return new DataSourceTransactionManager(source); }
        @Bean SqlSessionFactory sqlSessionFactory(DataSource source, MybatisPlusInterceptor interceptor, MetaObjectHandler handler) throws Exception {
            MybatisSqlSessionFactoryBean factory = new MybatisSqlSessionFactoryBean();
            factory.setDataSource(source);
            MybatisConfiguration configuration = new MybatisConfiguration();
            configuration.setMapUnderscoreToCamelCase(true);
            factory.setConfiguration(configuration);
            factory.setPlugins(interceptor);
            factory.setGlobalConfig(new GlobalConfig().setMetaObjectHandler(handler));
            return factory.getObject();
        }
        @Bean MapperFactoryBean<OrderInfoMapper> orders(SqlSessionFactory factory) {
            MapperFactoryBean<OrderInfoMapper> mapper = new MapperFactoryBean<>(OrderInfoMapper.class);
            mapper.setSqlSessionFactory(factory); return mapper;
        }
        @Bean MapperFactoryBean<OrderItemMapper> items(SqlSessionFactory factory) {
            MapperFactoryBean<OrderItemMapper> mapper = new MapperFactoryBean<>(OrderItemMapper.class);
            mapper.setSqlSessionFactory(factory); return mapper;
        }
        @Bean MapperFactoryBean<ProductMapper> products(SqlSessionFactory factory) {
            MapperFactoryBean<ProductMapper> mapper = new MapperFactoryBean<>(ProductMapper.class);
            mapper.setSqlSessionFactory(factory); return mapper;
        }
        @Bean MapperFactoryBean<com.aimall.backend.mapper.MallSkuMapper> skus(SqlSessionFactory factory) {
            var mapper = new MapperFactoryBean<>(com.aimall.backend.mapper.MallSkuMapper.class);
            mapper.setSqlSessionFactory(factory); return mapper;
        }
        @Bean RaceGate raceGate() { return new RaceGate(); }
        @Bean OrderSseNotifier notifier() { return mock(OrderSseNotifier.class); }
        @Bean OrderService orderService(OrderInfoMapper orders, OrderItemMapper items, ProductMapper products,
                                       OrderSseNotifier notifier, RaceGate gate, com.aimall.backend.mapper.MallSkuMapper skus) {
            // Keep real mapper/SQL; force both commands to finish reading the same stale state.
            OrderInfoMapper observed = (OrderInfoMapper) Proxy.newProxyInstance(OrderInfoMapper.class.getClassLoader(),
                    new Class<?>[]{OrderInfoMapper.class}, (proxy, method, args) -> {
                        Object value;
                        try { value = method.invoke(orders, args); }
                        catch (InvocationTargetException e) { throw e.getCause(); }
                        CyclicBarrier barrier = gate.afterRead;
                        if ("selectById".equals(method.getName()) && barrier != null) barrier.await(5, TimeUnit.SECONDS);
                        return value;
                    });
            ProductMapper observedProducts = (ProductMapper) Proxy.newProxyInstance(ProductMapper.class.getClassLoader(),
                    new Class<?>[]{ProductMapper.class}, (proxy, method, args) -> {
                        Object value;
                        try { value = method.invoke(products, args); }
                        catch (InvocationTargetException e) { throw e.getCause(); }
                        CyclicBarrier barrier = gate.afterProductRead;
                        if ("selectById".equals(method.getName()) && barrier != null && gate.productReads.incrementAndGet() <= 2) {
                            barrier.await(5, TimeUnit.SECONDS);
                        }
                        return value;
                    });
            return new OrderService(observed, items, observedProducts, skus, mock(com.aimall.backend.promotion.PromotionService.class), notifier, mock(AddressService.class));
        }
    }

    private AnnotationConfigApplicationContext context;
    private JdbcTemplate jdbc;
    private OrderService service;
    private OrderSseNotifier notifier;

    @BeforeEach void setUp() {
        context = new AnnotationConfigApplicationContext(Config.class);
        jdbc = context.getBean(JdbcTemplate.class);
        service = context.getBean(OrderService.class);
        notifier = context.getBean(OrderSseNotifier.class);
        createEntityTable("order_info", OrderInfo.class);
        createEntityTable("order_item", OrderItem.class);
        createEntityTable("product", Product.class);
        createEntityTable("mall_sku", MallSku.class);
        jdbc.execute("alter table order_item add constraint fk_test_order foreign key(order_id) references order_info(id)");
        jdbc.update("insert into product(id,name,status,price,stock,version) values(1,'Product','ON_SALE',10,3,1)");
        jdbc.update("insert into order_info(id,user_id,order_no,status,total_amount) values(30,7,'ORD-30','PENDING_PAYMENT',20)");
        jdbc.update("insert into order_item(order_id,product_id,quantity,price,subtotal) values(30,1,2,10,20)");
    }

    private void createEntityTable(String name, Class<?> entity) {
        List<String> columns = new ArrayList<>();
        for (var field : entity.getDeclaredFields()) {
            if (Modifier.isStatic(field.getModifiers())) continue;
            String column = field.getName().replaceAll("([a-z0-9])([A-Z])", "$1_$2").toLowerCase(Locale.ROOT);
            if ("id".equals(column)) { columns.add("id bigint generated by default as identity primary key"); continue; }
            Class<?> type = field.getType();
            String sqlType = type == Long.class ? "bigint" : type == Integer.class ? "integer"
                    : type == Boolean.class ? "boolean" : type == BigDecimal.class ? "decimal(18,2)"
                    : type == LocalDateTime.class ? "timestamp" : "varchar(4096)";
            columns.add(column + " " + sqlType + ("deleted".equals(column) ? " default 0" : ""));
        }
        jdbc.execute("create table " + name + "(" + String.join(",", columns) + ")");
    }

    @AfterEach void tearDown() { jdbc.execute("drop all objects"); context.close(); }

    private int race(Runnable first, Runnable second) throws Exception {
        context.getBean(RaceGate.class).afterRead = new CyclicBarrier(2);
        var executor = java.util.concurrent.Executors.newFixedThreadPool(2);
        try {
            List<java.util.concurrent.Future<Boolean>> futures = new ArrayList<>();
            for (Runnable command : List.of(first, second)) {
                futures.add(executor.submit(() -> {
                    try { command.run(); return true; }
                    catch (BizException e) { assertEquals(2004, e.getCode()); return false; }
                }));
            }
            int successes = 0;
            for (var future : futures) if (future.get(15, TimeUnit.SECONDS)) successes++;
            return successes;
        } finally { executor.shutdownNow(); context.getBean(RaceGate.class).afterRead = null; }
    }

    @Test void concurrentPaymentAndCancellationCannotBothWin() throws Exception {
        assertEquals(1, race(() -> service.pay(7L, 30L), () -> service.cancel(7L, 30L)));
        String state = jdbc.queryForObject("select status from order_info where id=30", String.class);
        assertTrue(List.of("PAID", "CANCELLED").contains(state));
        assertEquals("PAID".equals(state) ? 3 : 5, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test void duplicateConcurrentCancellationRestoresStockOnce() throws Exception {
        assertEquals(1, race(() -> service.cancel(7L, 30L), () -> service.cancel(7L, 30L)));
        assertEquals("CANCELLED", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertEquals(5, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test void outerRollbackRestoresOrderStateAndSuppressesNotification() {
        TransactionTemplate tx = new TransactionTemplate(context.getBean(PlatformTransactionManager.class));
        assertThrows(IllegalStateException.class, () -> tx.executeWithoutResult(status -> {
            service.pay(7L, 30L);
            throw new IllegalStateException("rollback after payment update");
        }));
        assertEquals("PENDING_PAYMENT", jdbc.queryForObject("select status from order_info where id=30", String.class));
        verifyNoInteractions(notifier);
    }

    @Test void stockRestorationFailureRollsBackCancellation() {
        jdbc.execute("alter table product add constraint reject_stock_restore check(stock <= 3)");
        assertThrows(RuntimeException.class, () -> service.cancel(7L, 30L));
        assertEquals("PENDING_PAYMENT", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        verifyNoInteractions(notifier);
    }

    @Test void creatingAnOrderAnnouncesOnlyAfterOuterCommit() {
        TransactionTemplate tx = new TransactionTemplate(context.getBean(PlatformTransactionManager.class));
        tx.executeWithoutResult(status -> {
            OrderDtos.CreateOrderRequest request = new OrderDtos.CreateOrderRequest();
            request.setProductId(1L); request.setQuantity(1);
            request.setReceiverName("Test Buyer"); request.setReceiverPhone("13800000000"); request.setReceiverAddress("Test address");
            service.create(7L, request, "USER", null);
            verifyNoInteractions(notifier);
        });
        verify(notifier).publish(any(OrderInfo.class));
        assertEquals(2, jdbc.queryForObject("select stock from product where id=1", Integer.class));
    }

    @Test void checkoutAnnouncesOnlyAfterOuterCommit() {
        TransactionTemplate tx = new TransactionTemplate(context.getBean(PlatformTransactionManager.class));
        tx.executeWithoutResult(status -> {
            service.checkout(7L, List.of(new OrderService.CheckoutItem(1L, 0L, 1)), null,
                    "Test Buyer", "13800000000", "Test address", null);
            verifyNoInteractions(notifier);
        });
        verify(notifier).publish(any(OrderInfo.class));
        assertEquals(2, jdbc.queryForObject("select stock from product where id=1", Integer.class));
    }

    @Test void checkoutOuterRollbackRestoresStockAndCreatedRowsWithoutNotification() {
        TransactionTemplate tx = new TransactionTemplate(context.getBean(PlatformTransactionManager.class));
        assertThrows(IllegalStateException.class, () -> tx.executeWithoutResult(status -> {
            service.checkout(7L, List.of(new OrderService.CheckoutItem(1L, 0L, 1)), null,
                    "Test Buyer", "13800000000", "Test address", null);
            throw new IllegalStateException("outer checkout failure");
        }));
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        assertEquals(1, jdbc.queryForObject("select count(*) from order_info", Integer.class));
        verifyNoInteractions(notifier);
    }

    @Test void outerActionFailureAfterCancelRestorationRollsEverythingBack() {
        TransactionTemplate tx = new TransactionTemplate(context.getBean(PlatformTransactionManager.class));
        assertThrows(IllegalStateException.class, () -> tx.executeWithoutResult(status -> {
            service.cancel(7L, 30L);
            throw new IllegalStateException("action confirmation could not be recorded");
        }));
        assertEquals("PENDING_PAYMENT", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        verifyNoInteractions(notifier);
    }

    @Test void concurrentCreationsCannotOversellRealVersionGuardedStock() throws Exception {
        context.getBean(RaceGate.class).afterProductRead = new CyclicBarrier(2);
        var pool = java.util.concurrent.Executors.newFixedThreadPool(2);
        try {
            java.util.concurrent.Callable<Boolean> create = () -> {
                var request = new OrderDtos.CreateOrderRequest();
                request.setProductId(1L); request.setQuantity(2);
                request.setReceiverName("Buyer"); request.setReceiverPhone("13800000000"); request.setReceiverAddress("Test address");
                try { service.create(7L, request, "USER", null); return true; }
                catch (BizException e) { assertEquals(2006, e.getCode()); return false; }
            };
            var first = pool.submit(create); var second = pool.submit(create);
            assertNotEquals(first.get(15, TimeUnit.SECONDS), second.get(15, TimeUnit.SECONDS));
        } finally { pool.shutdownNow(); }
        assertEquals(1, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        assertEquals(2, jdbc.queryForObject("select count(*) from order_info", Integer.class));
        assertEquals(2, jdbc.queryForObject("select count(*) from order_item", Integer.class));
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test void insufficientSkuRollsBackProductDeductionAndCreatedRows() {
        attachSku();
        jdbc.update("update mall_sku set stock=1 where id=99");
        assertEquals(2006, assertThrows(BizException.class, () -> service.checkout(7L,
                List.of(new OrderService.CheckoutItem(1L, 99L, 2)), null,
                "Buyer", "13800000000", "Test address", null)).getCode());
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        assertEquals(1, jdbc.queryForObject("select stock from mall_sku where id=99", Integer.class));
        assertEquals(1, jdbc.queryForObject("select count(*) from order_info", Integer.class));
        assertEquals(1, jdbc.queryForObject("select count(*) from order_item", Integer.class));
        verifyNoInteractions(notifier);
    }

    @Test void laterCheckoutItemFailureRollsBackEarlierStockDeduction() {
        assertEquals(2005, assertThrows(BizException.class, () -> service.checkout(7L,
                List.of(new OrderService.CheckoutItem(1L, null, 2), new OrderService.CheckoutItem(2L, null, 1)), null,
                "Buyer", "13800000000", "Test address", null)).getCode());
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        assertEquals(1, jdbc.queryForObject("select count(*) from order_info", Integer.class));
        assertEquals(1, jdbc.queryForObject("select count(*) from order_item", Integer.class));
        verifyNoInteractions(notifier);
    }
    private void attachSku() {
        jdbc.update("insert into mall_sku(id,product_id,status,price,stock,version) values(99,1,'ENABLE',12,3,1)");
        jdbc.update("update order_item set sku_id=99 where order_id=30");
    }

    @Test void deletedSkuMustRollBackProductRestockAndCancellation() {
        attachSku();
        jdbc.update("update mall_sku set deleted=1 where id=99");
        assertEquals(2108, assertThrows(BizException.class, () -> service.cancel(7L, 30L)).getCode());
        assertEquals("PENDING_PAYMENT", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        assertEquals(3, jdbc.queryForObject("select stock from mall_sku where id=99", Integer.class));
        verifyNoInteractions(notifier);
    }

    @Test void skuRestockSqlFailureRollsBackBothInventoriesAndCancellation() {
        attachSku();
        jdbc.execute("alter table mall_sku add constraint reject_sku_restore check(stock <= 3)");
        assertThrows(RuntimeException.class, () -> service.cancel(7L, 30L));
        assertEquals("PENDING_PAYMENT", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        assertEquals(3, jdbc.queryForObject("select stock from mall_sku where id=99", Integer.class));
        verifyNoInteractions(notifier);
    }

    @Test void duplicateConcurrentCancellationRestoresProductAndSkuExactlyOnce() throws Exception {
        attachSku();
        assertEquals(1, race(() -> service.cancel(7L, 30L), () -> service.cancel(7L, 30L)));
        assertEquals(5, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        assertEquals(5, jdbc.queryForObject("select stock from mall_sku where id=99", Integer.class));
        assertEquals(2004, assertThrows(BizException.class, () -> service.cancel(7L, 30L)).getCode());
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test void skuCheckoutAndCancellationRestoreOnlyTheReservedQuantity() {
        attachSku();
        OrderInfo order = service.checkout(7L, List.of(new OrderService.CheckoutItem(1L, 99L, 2)), null,
                "Buyer", "13800000000", "Test address", null);
        assertEquals(1, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        assertEquals(1, jdbc.queryForObject("select stock from mall_sku where id=99", Integer.class));
        service.cancel(7L, order.getId());
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        assertEquals(3, jdbc.queryForObject("select stock from mall_sku where id=99", Integer.class));
        verify(notifier, times(2)).publish(any(OrderInfo.class));
    }

    @Test void concurrentReceiptAndAutoDeliveryHaveOneWinnerAndPreserveTimestampOnRetry() throws Exception {
        jdbc.update("update order_info set status='SHIPPED' where id=30");
        assertEquals(1, race(() -> service.confirmReceipt(7L, 30L), () -> service.deliver(30L)));
        var delivered = jdbc.queryForObject("select delivered_at from order_info where id=30", java.sql.Timestamp.class);
        assertNotNull(delivered);
        assertEquals(2004, assertThrows(BizException.class, () -> service.confirmReceipt(7L, 30L)).getCode());
        assertEquals(delivered, jdbc.queryForObject("select delivered_at from order_info where id=30", java.sql.Timestamp.class));
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test void duplicateConcurrentPaymentOnlyUpdatesAndNotifiesOnce() throws Exception {
        assertEquals(1, race(() -> service.pay(7L, 30L), () -> service.pay(7L, 30L)));
        assertEquals("PAID", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertNotNull(jdbc.queryForObject("select paid_at from order_info where id=30", java.sql.Timestamp.class));
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test void nonOwnerCannotPayCancelOrReceiveWithRealSql() {
        assertEquals(2003, assertThrows(BizException.class, () -> service.pay(8L, 30L)).getCode());
        assertEquals(2003, assertThrows(BizException.class, () -> service.cancel(8L, 30L)).getCode());
        jdbc.update("update order_info set status='SHIPPED' where id=30");
        assertEquals(2003, assertThrows(BizException.class, () -> service.confirmReceipt(8L, 30L)).getCode());
        assertEquals("SHIPPED", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertNull(jdbc.queryForObject("select delivered_at from order_info where id=30", java.sql.Timestamp.class));
        verifyNoInteractions(notifier);
    }
    @Test void deletedProductMustNotSilentlyLoseCancellationRestock() {
        jdbc.update("update product set deleted=1 where id=1");
        BizException error = assertThrows(BizException.class, () -> service.cancel(7L, 30L));
        assertEquals(2005, error.getCode());
        assertEquals("PENDING_PAYMENT", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        verifyNoInteractions(notifier);
    }

    @Test void missingSkuMustRollBackProductRestockAndCancellation() {
        jdbc.update("update order_item set sku_id=99 where order_id=30");
        BizException error = assertThrows(BizException.class, () -> service.cancel(7L, 30L));
        assertEquals(2108, error.getCode());
        assertEquals("PENDING_PAYMENT", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertEquals(3, jdbc.queryForObject("select stock from product where id=1", Integer.class));
        verifyNoInteractions(notifier);
    }

    @Test void shippingMustPersistDeliveryCompanyAlongsideTrackingNumber() {
        jdbc.update("update order_info set status='PAID' where id=30");
        service.ship(30L, "TRACK-30", "Carrier");
        assertEquals("SHIPPED", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertEquals("Carrier", jdbc.queryForObject("select delivery_company from order_info where id=30", String.class));
        assertEquals("TRACK-30", jdbc.queryForObject("select logistics_no from order_info where id=30", String.class));
    }
    @Test void shipAndDeliverUseRealGuardedMapperWithTimestamps() {
        jdbc.update("update order_info set status='PAID' where id=30");
        service.ship(30L, "TRACK-30", null);
        assertEquals("SHIPPED", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertEquals("TRACK-30", jdbc.queryForObject("select logistics_no from order_info where id=30", String.class));
        assertNotNull(jdbc.queryForObject("select shipped_at from order_info where id=30", java.sql.Timestamp.class));
        service.deliver(30L);
        assertEquals("DELIVERED", jdbc.queryForObject("select status from order_info where id=30", String.class));
        assertNotNull(jdbc.queryForObject("select delivered_at from order_info where id=30", java.sql.Timestamp.class));
        verify(notifier, times(2)).publish(any(OrderInfo.class));
    }
}
