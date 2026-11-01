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
        @Bean com.aimall.backend.aftersale.AfterSaleService afterSaleWorkflow(){return mock(com.aimall.backend.aftersale.AfterSaleService.class);}
        @Bean com.aimall.backend.aftersale.AfterSaleEvidenceStorage afterSaleStorage(){return mock(com.aimall.backend.aftersale.AfterSaleEvidenceStorage.class);}
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
        table("after_sale", com.aimall.backend.entity.AfterSale.class);
        table("order_item", OrderItem.class);
        table("product", Product.class);
        table("mall_sku", MallSku.class);
        table("conversation", Conversation.class);
        table("agent_action", AgentAction.class);
        jdbc.execute("create unique index uk_agent_action_order on agent_action(order_id)");
        jdbc.execute("create unique index uk_agent_action_preparation on agent_action(user_id,conversation_id,preparation_key)");
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
            if ("action_id".equals(column) && "agent_action".equals(name)) { columns.add("action_id varchar(100) primary key"); continue; }
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

    @Test void preparationReplayReturnsOriginalSnapshotEvenAfterCatalogChanges() {
        var request = new AgentOrderActionService.PrepareRequest(7L, 20L, 10L, 2,
                "Buyer", "13800000000", "Test address", "call-create");
        var first = service.prepare(request);
        jdbc.update("update product set status='OFF_SALE', price=999 where id=10");
        var replay = service.prepare(request);
        assertEquals(first, replay);
        assertEquals(1, count("agent_action"));
        assertEquals(0, count("order_info"));
        assertThrows(BizException.class, () -> service.prepare(new AgentOrderActionService.PrepareRequest(
                7L, 20L, 10L, 3, "Buyer", "13800000000", "Test address", "call-create")));
        assertEquals(1, count("agent_action"));
    }

    @Test void concurrentPreparationUsesDatabaseUniqueness() throws Exception {
        var request = new AgentOrderActionService.PrepareRequest(7L, 20L, 10L, 2,
                "Buyer", "13800000000", "Test address", "call-parallel");
        var pool = Executors.newFixedThreadPool(2);
        var start = new CountDownLatch(1);
        try {
            Callable<String> call = () -> { start.await(); return service.prepare(request).actionId(); };
            var one = pool.submit(call); var two = pool.submit(call); start.countDown();
            assertEquals(one.get(15, TimeUnit.SECONDS), two.get(15, TimeUnit.SECONDS));
            assertEquals(1, count("agent_action"));
        } finally { pool.shutdownNow(); }
    }

    @Test void cancelAndAfterSalePreparationReplayAndPayloadBinding() {
        jdbc.update("insert into order_info(id,user_id,order_no,status,total_amount) values(30,7,'O30','PENDING_PAYMENT',20)");
        var cancel = new AgentOrderActionService.CancelPrepareRequest(7L, 20L, 30L, "Changed mind", "call-cancel");
        var first = service.prepareCancel(cancel);
        jdbc.update("update order_info set status='DELIVERED' where id=30");
        assertEquals(first, service.prepareCancel(cancel));
        assertThrows(BizException.class, () -> service.prepareCancel(new AgentOrderActionService.CancelPrepareRequest(
                7L, 20L, 30L, "Different reason", "call-cancel")));
        jdbc.update("insert into order_item(id,order_id,product_id,product_name,quantity,price,subtotal) values(40,30,10,'Product',2,10,20)");
        when(context.getBean(com.aimall.backend.aftersale.AfterSaleService.class)
                .quote(7L, 30L, 40L, "RETURN_REFUND", 1)).thenReturn(BigDecimal.TEN);
        var after = new AgentOrderActionService.AfterSalePrepareRequest(7L, 20L, 30L, 40L,
                "RETURN_REFUND", "QUALITY", "Broken", 1, "call-after");
        var prepared = service.prepareAfterSale(after);
        jdbc.update("update order_info set status='CANCELLED' where id=30");
        assertEquals(prepared, service.prepareAfterSale(after));
        assertThrows(BizException.class, () -> service.prepareAfterSale(new AgentOrderActionService.AfterSalePrepareRequest(
                7L, 20L, 30L, 40L, "RETURN_REFUND", "QUALITY", "Changed", 1, "call-after")));
        assertThrows(BizException.class, () -> service.prepareCancel(new AgentOrderActionService.CancelPrepareRequest(
                7L, 20L, 30L, "Broken", "call-after")));
        assertEquals(2, count("agent_action"));
        assertEquals(0, count("after_sale"));
    }

    @Test void canonicalSnapshotIsOwnerBoundAndStableThroughConfirmation() {
        String id = prepare();
        var before = service.snapshot(7L, id);
        assertEquals(Set.of("actionId", "userId", "conversationId", "type", "status", "expiresAt", "fingerprint"),
                new ObjectMapper().findAndRegisterModules().convertValue(before, Map.class).keySet());
        assertThrows(BizException.class, () -> service.snapshot(8L, id));
        service.confirm(7L, id, new AgentOrderActionService.ApprovalRequest("Edited", "13900000000", "Another address"));
        var after = service.snapshot(7L, id);
        assertEquals("CONFIRMED", after.status());
        assertEquals(before.fingerprint(), after.fingerprint());
        jdbc.update("update agent_action set amount=999, order_id=null where action_id=?", id);
        assertEquals(before.fingerprint(),service.snapshot(7L,id).fingerprint());
        jdbc.update("update conversation set user_id=8 where id=20");
        assertThrows(BizException.class, () -> service.snapshot(7L, id));
    }

    @Test void nativeStartRunsOnlyAfterPreparationCommitAndFailureReplaysSameAction() throws Exception {
        var props = new com.aimall.backend.config.AppProperties(); props.getAi().setActionWorkflowsEnabled(true);
        var client = mock(ActionWorkflowClient.class);
        var workflows = new ActionWorkflowCoordinator(service,client,props);
        var controller = new InternalToolController(context.getBean(ProductMapper.class),context.getBean(OrderInfoMapper.class),
                context.getBean(OrderService.class),context.getBean(ConversationMapper.class),service);
        org.springframework.test.util.ReflectionTestUtils.setField(controller,"workflows",workflows);
        var body = new InternalToolController.OrderCreateBody();
        body.setUserId(7L);body.setConversationId(20L);body.setProductId(10L);body.setQuantity(2);
        body.setReceiverName("Buyer");body.setReceiverPhone("13800000000");body.setReceiverAddress("Test address");
        body.setPreparationKey("call-start");
        when(client.invoke(any(),eq("start"),isNull(),isNull())).thenAnswer(inv -> {
            assertFalse(org.springframework.transaction.support.TransactionSynchronizationManager.isActualTransactionActive());
            assertEquals(1,count("agent_action"));
            throw new ActionWorkflowClient.GatewayException(((AgentOrderActionService.ActionSnapshot)inv.getArgument(0)).actionId(),503,true);
        });
        assertThrows(ActionWorkflowClient.GatewayException.class, () -> controller.orderPrepare(body));
        String id=jdbc.queryForObject("select action_id from agent_action",String.class);
        assertTrue(service.isNativeManaged(7L,id));
        jdbc.update("update agent_action set native_workflow_managed=false where action_id=?",id);
        assertTrue(service.status(7L,id).nativeManaged());
        assertTrue(service.isNativeManaged(7L,id));
        assertThrows(ActionWorkflowClient.GatewayException.class, () -> controller.orderPrepare(body));
        assertEquals(1,count("agent_action"));assertEquals(0,count("order_info"));
        String saved = jdbc.queryForObject("select preparation_result from agent_action where action_id=?",String.class,id);
        doAnswer(inv -> {
            assertFalse(org.springframework.transaction.support.TransactionSynchronizationManager.isActualTransactionActive());
            assertEquals(1,count("agent_action"));
            return new ActionWorkflowClient.WorkflowResult(id,"WAITING_APPROVAL",true,true,true,null,null);
        }).when(client).invoke(any(),eq("start"),isNull(),isNull());
        var data = new ObjectMapper().findAndRegisterModules().valueToTree(controller.orderPrepare(body).getData());
        assertEquals(id,data.get("actionId").asText());
        assertEquals("WAITING_APPROVAL",data.path("workflow").path("workflowStatus").asText());
        assertTrue(data.path("workflow").path("nativeInterrupt").asBoolean());
        assertEquals(saved,jdbc.queryForObject("select preparation_result from agent_action where action_id=?",String.class,id));
        assertFalse(new ObjectMapper().readTree(saved).has("workflow"));
        assertEquals(1,count("agent_action"));assertEquals(0,count("order_info"));
        props.getAi().setActionWorkflowsEnabled(false);
        assertThrows(BizException.class, () -> controller.orderPrepare(body));
        body.setPreparationKey(null);
        controller.orderPrepare(body);assertEquals(2,count("agent_action"));
    }

    @Test void keylessLegacyAdoptionCommitsProvenanceBeforeGatewayAndCannotDowngradeAfterFlagOff() {
        String id=prepare();
        var props=new com.aimall.backend.config.AppProperties();props.getAi().setActionWorkflowsEnabled(true);
        var client=mock(ActionWorkflowClient.class);
        var coordinator=new ActionWorkflowCoordinator(service,client,props);
        var controller=new com.aimall.backend.order.OrderActionController(service,coordinator);
        var json=new ObjectMapper().findAndRegisterModules();
        var before=json.valueToTree(controller.status(7L,id));
        assertTrue(before.path("data").has("nativeManaged"));
        assertFalse(before.path("data").path("nativeManaged").asBoolean());
        String fingerprint=service.snapshot(7L,id).fingerprint();
        when(client.invoke(any(),eq("start"),isNull(),isNull())).thenAnswer(inv -> {
            assertFalse(org.springframework.transaction.support.TransactionSynchronizationManager.isActualTransactionActive());
            assertEquals(Boolean.TRUE,jdbc.queryForObject("select native_workflow_managed from agent_action where action_id=?",Boolean.class,id));
            assertNull(jdbc.queryForObject("select preparation_key from agent_action where action_id=?",String.class,id));
            return new ActionWorkflowClient.WorkflowResult(id,"WAITING_APPROVAL",true,true,true,null,null);
        });
        var approval=new AgentOrderActionService.ApprovalRequest("Approved","13900000000","Approved address");
        when(client.invoke(any(),eq("resume"),eq("approve"),eq(approval))).thenReturn(
                new ActionWorkflowClient.WorkflowResult(id,"EXECUTING",true,false,true,null,null));
        controller.confirm(7L,id,approval);
        assertTrue(service.isNativeManaged(7L,id));
        assertTrue(json.valueToTree(controller.status(7L,id)).path("data").path("nativeManaged").asBoolean());
        assertEquals(fingerprint,service.snapshot(7L,id).fingerprint());
        props.getAi().setActionWorkflowsEnabled(false);
        assertTrue(json.valueToTree(controller.status(7L,id)).path("data").path("nativeManaged").asBoolean());
        assertThrows(BizException.class,()->controller.confirm(7L,id,
                new AgentOrderActionService.ApprovalRequest("Replacement","13800000000","Different address")));
        assertThrows(BizException.class,()->controller.cancel(7L,id));
        var legacy=new InternalToolController(context.getBean(ProductMapper.class),context.getBean(OrderInfoMapper.class),
                context.getBean(OrderService.class),context.getBean(ConversationMapper.class),service);
        org.springframework.test.util.ReflectionTestUtils.setField(legacy,"workflows",coordinator);
        var body=new InternalToolController.OrderConfirmBody();body.setUserId(7L);body.setActionId(id);
        assertThrows(BizException.class,()->legacy.orderConfirm(body));
        assertEquals(0,count("order_info"));assertEquals(5,stock());
    }

    @Test void lostRegistrationOfKeylessLegacyActionStillPersistsFailClosedProvenance() {
        String id=prepare();
        var props=new com.aimall.backend.config.AppProperties();props.getAi().setActionWorkflowsEnabled(true);
        var client=mock(ActionWorkflowClient.class);
        var coordinator=new ActionWorkflowCoordinator(service,client,props);
        when(client.invoke(any(),eq("start"),isNull(),isNull())).thenThrow(new ActionWorkflowClient.GatewayException(id,503,true));
        assertThrows(ActionWorkflowClient.GatewayException.class,()->coordinator.recover(7L,id));
        assertTrue(service.status(7L,id).nativeManaged());
        props.getAi().setActionWorkflowsEnabled(false);
        assertThrows(BizException.class,()->coordinator.requiresNative(7L,id));
        assertEquals(0,count("order_info"));
    }

    @Test void nativeAdoptionRequiresOwnerAndConversationAndMarkerWriteIsTransactional() {
        String id=prepare();
        assertThrows(BizException.class,()->service.markNativeManaged(8L,id));
        assertFalse(service.isNativeManaged(7L,id));
        assertThrows(IllegalStateException.class,()->tx.executeWithoutResult(ignored -> {
            service.markNativeManaged(7L,id);
            assertTrue(service.isNativeManaged(7L,id));
            throw new IllegalStateException("roll back adoption");
        }));
        assertFalse(service.isNativeManaged(7L,id));
        jdbc.update("update conversation set user_id=8 where id=20");
        assertThrows(BizException.class,()->service.markNativeManaged(7L,id));
        assertFalse(service.isNativeManaged(7L,id));
    }

    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(strings={"CONFIRMED","CANCELLED","EXPIRED"})
    void unmanagedTerminalLegacyRecoveryRejectsWithoutPersistingNativeProvenance(String status) {
        String id=prepare();
        if ("CONFIRMED".equals(status)) service.confirm(7L,id);
        else if ("CANCELLED".equals(status)) service.cancel(7L,id);
        else {
            jdbc.update("update agent_action set expires_at=? where action_id=?",
                    java.sql.Timestamp.from(context.getBean(Clock.class).instant().minusSeconds(1)),id);
            service.expirePendingActions();
        }
        assertEquals(status,service.snapshot(7L,id).status());
        assertFalse(service.status(7L,id).nativeManaged());
        int orders=count("order_info");int originalStock=stock();
        var props=new com.aimall.backend.config.AppProperties();props.getAi().setActionWorkflowsEnabled(true);
        var client=mock(ActionWorkflowClient.class);
        // Before the fix, Java would commit adoption and only then receive Python's missing-checkpoint rejection.
        when(client.invoke(any(),eq("start"),isNull(),isNull())).thenThrow(new ActionWorkflowClient.GatewayException(id,409,false));
        var coordinator=new ActionWorkflowCoordinator(service,client,props);
        var controller=new com.aimall.backend.order.OrderActionController(service,coordinator);
        var failure=assertThrows(RuntimeException.class,()->controller.recover(7L,id));
        assertFalse(service.isNativeManaged(7L,id));
        assertFalse(service.status(7L,id).nativeManaged());
        assertFalse(Boolean.TRUE.equals(jdbc.queryForObject("select native_workflow_managed from agent_action where action_id=?",Boolean.class,id)));
        assertEquals(2004,assertInstanceOf(BizException.class,failure).getCode());
        verifyNoInteractions(client);
        assertEquals(orders,count("order_info"));assertEquals(originalStock,stock());
        assertEquals(status,service.snapshot(7L,id).status());
    }

    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(strings={"CONFIRMED","CANCELLED","EXPIRED"})
    void terminalTransitionAfterCoordinatorReadCannotRaceNativeAdmission(String terminalStatus) {
        String id=prepare();
        var props=new com.aimall.backend.config.AppProperties();props.getAi().setActionWorkflowsEnabled(true);
        var client=mock(ActionWorkflowClient.class);
        var racedActions=mock(AgentOrderActionService.class,org.mockito.AdditionalAnswers.delegatesTo(service));
        doAnswer(inv -> {
            var pending=service.snapshot(7L,id);
            assertEquals("PENDING",pending.status());
            if ("CONFIRMED".equals(terminalStatus)) service.confirm(7L,id);
            else if ("CANCELLED".equals(terminalStatus)) service.cancel(7L,id);
            else jdbc.update("update agent_action set expires_at=? where action_id=?",
                    java.sql.Timestamp.from(context.getBean(Clock.class).instant().minusSeconds(1)),id);
            return pending;
        }).when(racedActions).snapshot(7L,id);
        when(client.invoke(any(),eq("start"),isNull(),isNull())).thenThrow(new ActionWorkflowClient.GatewayException(id,409,false));
        var coordinator=new ActionWorkflowCoordinator(racedActions,client,props);
        var failure=assertThrows(RuntimeException.class,()->coordinator.recover(7L,id));
        assertFalse(service.isNativeManaged(7L,id));
        assertFalse(service.status(7L,id).nativeManaged());
        assertEquals(2004,assertInstanceOf(BizException.class,failure).getCode());
        verifyNoInteractions(client);
        assertEquals(terminalStatus,service.snapshot(7L,id).status());
        if ("EXPIRED".equals(terminalStatus)) assertEquals("PENDING",status(id),"expiry must be computed under the row lock without relying on the sweeper");
        // The locked guard must still permit the same terminal state when provenance already exists.
        jdbc.update("update agent_action set native_workflow_managed=true where action_id=?",id);
        assertDoesNotThrow(()->service.markNativeManaged(7L,id));
        assertTrue(service.status(7L,id).nativeManaged());
    }

    @Test void callbackReplayAfterBusinessCommitReturnsSameReceiptWithoutAnotherOrderOrStockDeduction() {
        var props=new com.aimall.backend.config.AppProperties();props.getAi().setActionWorkflowsEnabled(true);
        var coordinator=new ActionWorkflowCoordinator(service,mock(ActionWorkflowClient.class),props);
        var controller=new ActionWorkflowController(service,coordinator);
        String id=service.prepare(new AgentOrderActionService.PrepareRequest(7L,20L,10L,2,
                "Original","13800000000","Original address","call-execute")).actionId();
        var before=service.snapshot(7L,id);
        var approved=new AgentOrderActionService.ApprovalRequest("Edited","13900000000","Edited address");
        var execute=new ActionWorkflowController.ExecuteBody(7L,id,approved);
        var first=controller.execute(execute).getData();
        // Model a lost callback response/checkpoint after the business transaction has committed.
        var replay=controller.execute(execute).getData();
        assertEquals(first,replay);assertEquals("Edited address",replay.get("receiverAddress"));
        assertEquals(1,count("order_info"));assertEquals(1,count("order_item"));assertEquals(3,stock());
        assertEquals(before.fingerprint(),service.snapshot(7L,id).fingerprint());
        props.getAi().setActionWorkflowsEnabled(false);
        assertThrows(BizException.class,()->controller.execute(execute));
        assertThrows(BizException.class,()->controller.cancel(new ActionWorkflowController.ActionBody(7L,id)));
        assertEquals(1,count("order_info"));
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
        assertEquals(String.valueOf(order.getId()), cache.get("ai:order:action:" + id));
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

    @Test void differentApprovedActionsInOneConversationDoNotReuseAnOlderOrder() {
        String first=service.prepare(new AgentOrderActionService.PrepareRequest(7L,20L,10L,1,"Buyer","13800000000","First address")).actionId();
        OrderInfo old=service.confirm(7L,first);
        String second=service.prepare(new AgentOrderActionService.PrepareRequest(7L,20L,10L,2,"Buyer","13800000000","Second address")).actionId();
        OrderInfo current=service.confirm(7L,second);
        assertNotEquals(old.getId(),current.getId());assertEquals(2,count("order_info"));assertEquals(2,stock());
        assertEquals("Second address",current.getReceiverAddress());assertEquals(2,jdbc.queryForObject("select quantity from order_item where order_id=?",Integer.class,current.getId()));
    }
    @Test void aCancelledOrderCannotSatisfyANewlyApprovedAction() {
        String first=prepare();OrderInfo old=service.confirm(7L,first);context.getBean(OrderService.class).cancel(7L,old.getId());
        String second=prepare();OrderInfo current=service.confirm(7L,second);
        assertNotEquals(old.getId(),current.getId());assertEquals("PENDING_PAYMENT",current.getStatus());assertEquals(3,stock());
    }
    @Test void priceChangeAfterProposalRequiresRenewedApprovalAndDoesNotReserveStock() {
        String action=prepare();jdbc.update("update product set price=12,version=version+1 where id=10");
        BizException error=assertThrows(BizException.class,()->service.confirm(7L,action));
        assertEquals(2015,error.getCode());assertEquals("PENDING",status(action));assertEquals(0,count("order_info"));assertEquals(5,stock());assertTrue(cache.isEmpty());
    }
}
