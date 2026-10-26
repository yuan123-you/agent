package com.aimall.backend.internal;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.config.MybatisPlusConfig;
import com.aimall.backend.entity.*;
import com.aimall.backend.mapper.*;
import com.aimall.backend.order.OrderService;
import com.aimall.backend.order.OrderSseNotifier;
import com.aimall.backend.promotion.PromotionService;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.config.GlobalConfig;
import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.spring.MybatisSqlSessionFactoryBean;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.lang.reflect.Modifier;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import javax.sql.DataSource;
import org.apache.ibatis.session.SqlSessionFactory;
import org.junit.jupiter.api.*;
import org.mybatis.spring.mapper.MapperFactoryBean;
import org.springframework.context.annotation.*;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import org.springframework.transaction.support.TransactionTemplate;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** Real mapper SQL and Spring transactions on a private in-memory database; no application config or Redis server. */
class AgentOrderActionTransactionTest {
    @Configuration
    @EnableTransactionManagement(proxyTargetClass = true)
    @Import(MybatisPlusConfig.class)
    static class Config {
        @Bean Clock clock() { return Clock.fixed(Instant.parse("2026-10-26T04:00:00Z"), ZoneOffset.UTC); }
        @Bean DataSource dataSource() {
            return new DriverManagerDataSource("jdbc:h2:mem:agent_orders_" + UUID.randomUUID()
                    + ";MODE=MySQL;DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=10000", "sa", "");
        }
        @Bean JdbcTemplate jdbc(DataSource source) { return new JdbcTemplate(source); }
        @Bean PlatformTransactionManager transactionManager(DataSource source) { return new DataSourceTransactionManager(source); }
        @Bean SqlSessionFactory sqlSessionFactory(DataSource source, MybatisPlusInterceptor interceptor, MetaObjectHandler handler) throws Exception {
            var factory = new MybatisSqlSessionFactoryBean();
            factory.setDataSource(source);
            var configuration = new MybatisConfiguration();
            configuration.setMapUnderscoreToCamelCase(true);
            factory.setConfiguration(configuration);
            factory.setPlugins(interceptor);
            factory.setGlobalConfig(new GlobalConfig().setMetaObjectHandler(handler));
            return factory.getObject();
        }
        private <T> MapperFactoryBean<T> mapper(Class<T> type, SqlSessionFactory factory) {
            var mapper = new MapperFactoryBean<>(type); mapper.setSqlSessionFactory(factory); return mapper;
        }
        @Bean MapperFactoryBean<OrderInfoMapper> orders(SqlSessionFactory f) { return mapper(OrderInfoMapper.class, f); }
        @Bean MapperFactoryBean<OrderItemMapper> items(SqlSessionFactory f) { return mapper(OrderItemMapper.class, f); }
        @Bean MapperFactoryBean<ProductMapper> products(SqlSessionFactory f) { return mapper(ProductMapper.class, f); }
        @Bean MapperFactoryBean<MallSkuMapper> skus(SqlSessionFactory f) { return mapper(MallSkuMapper.class, f); }
        @Bean MapperFactoryBean<ConversationMapper> conversations(SqlSessionFactory f) { return mapper(ConversationMapper.class, f); }
        @Bean MapperFactoryBean<AgentActionMapper> actions(SqlSessionFactory f) { return mapper(AgentActionMapper.class, f); }
        @Bean OrderSseNotifier notifier() { return mock(OrderSseNotifier.class); }
        @Bean StringRedisTemplate redis() { return mock(StringRedisTemplate.class); }
        @Bean AddressService addresses() { return mock(AddressService.class); }
        @Bean OrderService orderService(OrderInfoMapper orders, OrderItemMapper items, ProductMapper products,
                                       MallSkuMapper skus, OrderSseNotifier notifier, AddressService addresses) {
            return new OrderService(orders, items, products, skus, mock(PromotionService.class), notifier, addresses);
        }
        @Bean AgentOrderActionService agentService(AddressService addresses, AgentActionMapper actions,
                ProductMapper products, ConversationMapper conversations, OrderInfoMapper orders,
                OrderItemMapper items, OrderService service, StringRedisTemplate redis, Clock clock) {
            return new AgentOrderActionService(addresses, actions, products, conversations, orders, items,
                    mock(AfterSaleMapper.class), service, redis, new ObjectMapper(), clock);
        }
    }

    private AnnotationConfigApplicationContext context;
    private JdbcTemplate jdbc;
    private AgentOrderActionService service;
    private OrderSseNotifier notifier;
    private TransactionTemplate tx;
    private final Map<String, String> cache = new ConcurrentHashMap<>();
    private ValueOperations<String, String> values;

    @SuppressWarnings("unchecked")
    @BeforeEach void setUp() {
        context = new AnnotationConfigApplicationContext(Config.class);
        jdbc = context.getBean(JdbcTemplate.class);
        service = context.getBean(AgentOrderActionService.class);
        notifier = context.getBean(OrderSseNotifier.class);
        tx = new TransactionTemplate(context.getBean(PlatformTransactionManager.class));
        table("order_info", OrderInfo.class);
        table("order_item", OrderItem.class);
        table("product", Product.class);
        table("mall_sku", MallSku.class);
        table("conversation", Conversation.class);
        table("agent_action", AgentAction.class);
        jdbc.execute("create unique index uk_agent_action_order on agent_action(order_id)");
        jdbc.update("insert into product(id,name,status,price,stock,version) values(10,'Product','ON_SALE',10,5,1)");
        jdbc.update("insert into conversation(id,user_id) values(20,7)");
        values = mock(ValueOperations.class);
        when(context.getBean(StringRedisTemplate.class).opsForValue()).thenReturn(values);
        when(values.get(anyString())).thenAnswer(inv -> cache.get(inv.getArgument(0)));
        doAnswer(inv -> { cache.put(inv.getArgument(0), inv.getArgument(1)); return null; })
                .when(values).set(anyString(), anyString(), any(Duration.class));
    }

    private void table(String name, Class<?> entity) {
        var columns = new ArrayList<String>();
        for (var field : entity.getDeclaredFields()) {
            if (Modifier.isStatic(field.getModifiers())) continue;
            String column = field.getName().replaceAll("([a-z0-9])([A-Z])", "$1_$2").toLowerCase(Locale.ROOT);
            if ("id".equals(column)) { columns.add("id bigint generated by default as identity primary key"); continue; }
            if ("action_id".equals(column)) { columns.add("action_id varchar(100) primary key"); continue; }
            Class<?> type = field.getType();
            String sqlType = type == Long.class ? "bigint" : type == Integer.class ? "integer"
                    : type == Boolean.class ? "boolean" : type == BigDecimal.class ? "decimal(18,2)"
                    : type == LocalDateTime.class || type == Instant.class ? "timestamp" : "varchar(4096)";
            columns.add(column + " " + sqlType + ("deleted".equals(column) ? " default 0" : ""));
        }
        jdbc.execute("create table " + name + "(" + String.join(",", columns) + ")");
    }
    @AfterEach void close() { jdbc.execute("drop all objects"); context.close(); }
    private String prepare() {
        return service.prepare(new AgentOrderActionService.PrepareRequest(7L, 20L, 10L, 2,
                "Buyer", "13800000000", "Test address")).actionId();
    }
    private int stock() { return jdbc.queryForObject("select stock from product where id=10", Integer.class); }
    private int count(String table) { return jdbc.queryForObject("select count(*) from " + table, Integer.class); }
    private String status(String id) {
        return jdbc.queryForObject("select status from agent_action where action_id=?", String.class, id);
    }

    @Test void outerRollbackMustNotPublishAnUncommittedOrderToIdempotencyCache() {
        String id = prepare();
        assertThrows(IllegalStateException.class, () -> tx.executeWithoutResult(s -> {
            service.confirm(7L, id);
            throw new IllegalStateException("outer action failed");
        }));
        assertEquals("PENDING", status(id));
        assertEquals(5, stock());
        assertEquals(0, count("order_info"));
        assertEquals(0, count("order_item"));
        verifyNoInteractions(notifier);
        assertTrue(cache.isEmpty(), "rolled-back order must not survive in Redis");
    }

    @Test void idempotencyCacheMustBePublishedOnlyAfterOuterCommit() {
        String id = prepare();
        OrderInfo order = tx.execute(s -> {
            OrderInfo created = service.confirm(7L, id);
            assertTrue(cache.isEmpty(), "uncommitted order is not a valid idempotency result");
            verifyNoInteractions(notifier);
            return created;
        });
        assertEquals(String.valueOf(order.getId()), cache.get("ai:order:20:10"));
        assertEquals("CONFIRMED", status(id));
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test void concurrentConfirmationsOfOneActionCreateAndDeductExactlyOnce() throws Exception {
        String id = prepare();
        var pool = Executors.newFixedThreadPool(2);
        var start = new CyclicBarrier(2);
        try {
            Callable<OrderInfo> confirm = () -> { start.await(5, TimeUnit.SECONDS); return service.confirm(7L, id); };
            var first = pool.submit(confirm); var second = pool.submit(confirm);
            assertEquals(first.get(15, TimeUnit.SECONDS).getId(), second.get(15, TimeUnit.SECONDS).getId());
        } finally { pool.shutdownNow(); }
        assertEquals("CONFIRMED", status(id));
        assertEquals(3, stock());
        assertEquals(1, count("order_info"));
        assertEquals(1, count("order_item"));
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test void failedActionConfirmationRollsBackRealOrderItemsAndStock() {
        String id = prepare();
        jdbc.execute("alter table agent_action add constraint reject_confirm check(status <> 'CONFIRMED')");
        assertThrows(RuntimeException.class, () -> service.confirm(7L, id));
        assertEquals("PENDING", status(id));
        assertEquals(5, stock());
        assertEquals(0, count("order_info"));
        assertEquals(0, count("order_item"));
        assertTrue(cache.isEmpty());
        verifyNoInteractions(notifier);
    }

    @Test void otherUserCannotConfirmOrCancelAction() {
        String id = prepare();
        assertEquals(2003, assertThrows(BizException.class, () -> service.confirm(8L, id)).getCode());
        assertEquals(2003, assertThrows(BizException.class, () -> service.cancel(8L, id)).getCode());
        assertEquals("PENDING", status(id));
        assertEquals(5, stock());
        assertEquals(0, count("order_info"));
        assertTrue(cache.isEmpty());
    }

    @Test void concurrentConfirmAndCancelOfOneActionHaveOneWinner() throws Exception {
        String id = prepare();
        var pool = Executors.newFixedThreadPool(2);
        var start = new CyclicBarrier(2);
        try {
            var confirm = pool.submit(() -> {
                start.await(5, TimeUnit.SECONDS);
                try { service.confirm(7L, id); return true; }
                catch (BizException e) { assertEquals(2012, e.getCode()); return false; }
            });
            var cancel = pool.submit(() -> {
                start.await(5, TimeUnit.SECONDS);
                try { service.cancel(7L, id); return true; }
                catch (BizException e) { assertEquals(2012, e.getCode()); return false; }
            });
            assertNotEquals(confirm.get(15, TimeUnit.SECONDS), cancel.get(15, TimeUnit.SECONDS));
        } finally { pool.shutdownNow(); }
        boolean confirmed = "CONFIRMED".equals(status(id));
        assertEquals(confirmed ? 1 : 0, count("order_info"));
        assertEquals(confirmed ? 1 : 0, count("order_item"));
        assertEquals(confirmed ? 3 : 5, stock());
        if (confirmed) verify(notifier).publish(any(OrderInfo.class));
        else { assertTrue(cache.isEmpty()); verifyNoInteractions(notifier); }
    }

    private OrderInfo userOrder() {
        var request = new com.aimall.backend.order.OrderDtos.CreateOrderRequest();
        request.setProductId(10L); request.setQuantity(2);
        request.setReceiverName("Buyer"); request.setReceiverPhone("13800000000"); request.setReceiverAddress("Test address");
        return context.getBean(OrderService.class).create(7L, request, "USER", null);
    }

    @Test void repeatedBusinessCancelRestoresInventoryExactlyOnce() {
        OrderInfo order = userOrder();
        clearInvocations(notifier);
        String id = service.prepareCancel(new AgentOrderActionService.CancelPrepareRequest(7L, 20L, order.getId(), "Cancel")).actionId();
        assertEquals("CANCELLED", service.confirmBusiness(7L, id).orderStatus());
        assertEquals("CANCELLED", service.confirmBusiness(7L, id).orderStatus());
        assertEquals(5, stock());
        assertEquals("CONFIRMED", status(id));
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test void failedBusinessActionConfirmationRollsBackCancellationAndStockRestoration() {
        OrderInfo order = userOrder();
        clearInvocations(notifier);
        String id = service.prepareCancel(new AgentOrderActionService.CancelPrepareRequest(7L, 20L, order.getId(), "Cancel")).actionId();
        jdbc.execute("alter table agent_action add constraint reject_confirm check(status <> 'CONFIRMED')");
        assertThrows(RuntimeException.class, () -> service.confirmBusiness(7L, id));
        assertEquals("PENDING", status(id));
        assertEquals("PENDING_PAYMENT", jdbc.queryForObject("select status from order_info where id=?", String.class, order.getId()));
        assertEquals(3, stock());
        verifyNoInteractions(notifier);
    }

    @Test void expiredConfirmationDoesNotCreateAnOrder() {
        String id = prepare();
        jdbc.update("update agent_action set expires_at=? where action_id=?", java.sql.Timestamp.from(context.getBean(Clock.class).instant()), id);
        assertEquals(2011, assertThrows(BizException.class, () -> service.confirm(7L, id)).getCode());
        assertEquals(0, count("order_info"));
        assertEquals(5, stock());
        assertTrue(cache.isEmpty());
        verifyNoInteractions(notifier);
    }
    @Test void redisWriteFailureCannotTurnCommittedOrderIntoReportedFailure() {
        String id = prepare();
        doThrow(new IllegalStateException("cache unavailable")).when(values).set(anyString(), anyString(), any(Duration.class));
        OrderInfo order = service.confirm(7L, id);
        assertEquals("CONFIRMED", status(id));
        assertEquals(1, count("order_info"));
        assertEquals(3, stock());
        assertEquals(order.getId(), service.confirm(7L, id).getId());
        verify(notifier).publish(any(OrderInfo.class));
    }
}
