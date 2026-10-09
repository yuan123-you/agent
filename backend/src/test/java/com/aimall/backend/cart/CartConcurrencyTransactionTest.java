package com.aimall.backend.cart;
import com.aimall.backend.order.*;
import com.aimall.backend.entity.CartItem;
import com.aimall.backend.mapper.CartItemMapper;
import java.util.Map;
import java.util.HashMap;
import java.util.concurrent.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.config.MybatisPlusConfig;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.OrderItem;
import com.aimall.backend.entity.Product;
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

class CartConcurrencyTransactionTest {
    static class RaceGate {
        volatile CyclicBarrier afterRead, beforeInsert;
        volatile CountDownLatch snapshot, release;
        volatile boolean failDelete, missDelete;
    }
    @Configuration
    @EnableTransactionManagement(proxyTargetClass = true)
    @Import(MybatisPlusConfig.class)
    static class Config {
        @Bean Clock clock() { return Clock.systemDefaultZone(); }
        @Bean DataSource dataSource() {
            return new DriverManagerDataSource("jdbc:h2:mem:cart_" + UUID.randomUUID()
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
        @Bean MapperFactoryBean<CartItemMapper> carts(SqlSessionFactory factory) {
            MapperFactoryBean<CartItemMapper> mapper = new MapperFactoryBean<>(CartItemMapper.class);
            mapper.setSqlSessionFactory(factory); return mapper;
        }
        @Bean CartController controller(CartItemMapper cart, ProductMapper products, OrderService orders, RaceGate gate) {
            CartItemMapper observed = (CartItemMapper) Proxy.newProxyInstance(CartItemMapper.class.getClassLoader(),
                    new Class<?>[]{CartItemMapper.class}, (proxy, method, args) -> {
                        if (method.getName().equals("insertGuarded") && gate.beforeInsert != null)
                            gate.beforeInsert.await(5, TimeUnit.SECONDS);
                        if (method.getName().equals("delete")) {
                            if (gate.failDelete) throw new IllegalStateException("injected cart persistence failure");
                            if (gate.missDelete) return 0;
                        }
                        Object result;
                        try { result = method.invoke(cart, args); }
                        catch (InvocationTargetException e) { throw e.getCause(); }
                        if (method.getName().equals("selectOne") && gate.afterRead != null) gate.afterRead.await(5, TimeUnit.SECONDS);
                        if (method.getName().equals("selectList") && gate.snapshot != null) {
                            gate.snapshot.countDown();
                            if (!gate.release.await(5, TimeUnit.SECONDS)) throw new AssertionError("snapshot timeout");
                        }
                        return result;
                    });
            return new CartController(observed, products, orders);
        }
        @Bean RaceGate raceGate() { return new RaceGate(); }
        @Bean OrderSseNotifier notifier() { return mock(OrderSseNotifier.class); }
        @Bean OrderService orderService(OrderInfoMapper orders, OrderItemMapper items, ProductMapper products,
                                       OrderSseNotifier notifier, RaceGate gate) {
            return new OrderService(orders, items, products, notifier, mock(AddressService.class));
        }
    }

    private AnnotationConfigApplicationContext context;
    private JdbcTemplate jdbc;
    private CartController controller;
    private RaceGate gate;
    @BeforeEach void setup() {
        context = new AnnotationConfigApplicationContext(Config.class);
        jdbc = context.getBean(JdbcTemplate.class); controller = context.getBean(CartController.class); gate = context.getBean(RaceGate.class);
        table("cart_item", CartItem.class); table("product", Product.class); table("order_info", OrderInfo.class); table("order_item", OrderItem.class);
        jdbc.execute("alter table cart_item add constraint uk_user_product unique(user_id,product_id)");
        jdbc.update("insert into product(id,name,status,price,stock,version,deleted) values(1,'Product','ON_SALE',10,1000,1,0)");
    }
    private void table(String name, Class<?> entity) {
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
    @AfterEach void close() { jdbc.execute("drop all objects"); context.close(); }
    private void row(int qty) { jdbc.update("insert into cart_item(id,user_id,product_id,quantity,checked) values(1,7,1,?,1)",qty); }
    private CartController.AddBody addBody(Integer qty) { var b = new CartController.AddBody(); b.setProductId(1L); b.setQuantity(qty); return b; }
    private CartController.CheckoutBody checkoutBody() {
        var b = new CartController.CheckoutBody(); b.setReceiverName("Receiver"); b.setReceiverPhone("13800000000"); b.setReceiverAddress("Test address"); return b;
    }
    private int qty() { return jdbc.queryForObject("select quantity from cart_item where user_id=7 and product_id=1",Integer.class); }
    private int count(String table) { return jdbc.queryForObject("select count(*) from " + table,Integer.class); }
    private void twoAdds() throws Exception {
        gate.afterRead = new CyclicBarrier(2); var pool = Executors.newFixedThreadPool(2);
        try {
            var start = new CyclicBarrier(2);
            var a = pool.submit(() -> { start.await(); controller.add(7L,addBody(2)); return true; });
            var b = pool.submit(() -> { start.await(); controller.add(7L,addBody(2)); return true; });
            assertTrue(a.get(15,TimeUnit.SECONDS)); assertTrue(b.get(15,TimeUnit.SECONDS));
        } finally { pool.shutdownNow(); }
    }
    @Test void concurrentExistingAddsDoNotLoseIncrements() throws Exception { row(1); twoAdds(); assertEquals(5,qty()); }
    @Test void concurrentFirstAddsUseUniqueRowAndRetainBothQuantities() throws Exception { gate.beforeInsert = new CyclicBarrier(2); twoAdds(); assertEquals(1,count("cart_item")); assertEquals(4,qty()); }
    @Test void firstInsertCannotExceedStock() { jdbc.update("update product set stock=1"); assertThrows(BizException.class, () -> controller.add(7L,addBody(2))); assertEquals(0,count("cart_item")); }
    @ParameterizedTest @NullSource @ValueSource(ints = {-1,0,100,Integer.MAX_VALUE})
    void invalidAddQuantityIsBusinessErrorWithoutMutation(Integer quantity) { assertThrows(BizException.class, () -> controller.add(7L,addBody(quantity))); assertEquals(0,count("cart_item")); }
    @Test void accumulatedQuantityIsNotCappedAt99() { row(99); controller.add(7L,addBody(99)); assertEquals(198,qty()); }
    @ParameterizedTest @NullSource @ValueSource(strings = {"-1","0","1.5","2147483648","abc"})
    void invalidUpdateQuantityIsBusinessErrorWithoutMutation(String raw) {
        row(2); var body = new HashMap<String,Object>(); body.put("quantity",raw == null ? null : raw.equals("abc") ? raw : new BigDecimal(raw));
        assertThrows(BizException.class, () -> controller.update(7L,1L,body)); assertEquals(2,qty());
    }
    @Test void foreignUserCannotUpdateOrDelete() {
        row(2); assertThrows(BizException.class, () -> controller.update(8L,1L,Map.of("quantity",3))); assertThrows(BizException.class, () -> controller.remove(8L,1L)); assertEquals(2,qty());
    }
    @Test void cartDeleteFailureRollsBackOrderItemsStockAndNotifications() {
        row(2); gate.failDelete = true; assertThrows(IllegalStateException.class, () -> controller.checkout(7L,checkoutBody()));
        assertEquals(0,count("order_info")); assertEquals(0,count("order_item")); assertEquals(1000,jdbc.queryForObject("select stock from product",Integer.class)); assertEquals(2,qty()); verifyNoInteractions(context.getBean(OrderSseNotifier.class));
    }
    @Test void zeroAffectedCleanupMustNotReportCheckoutSuccess() {
        row(2); gate.missDelete = true; assertThrows(BizException.class, () -> controller.checkout(7L,checkoutBody())); assertEquals(0,count("order_info")); assertEquals(2,qty());
    }
    @Test void orderFailureLeavesCartAndStockUntouched() {
        row(2); jdbc.execute("alter table order_item add constraint forced_failure check(quantity < 0)"); assertThrows(RuntimeException.class, () -> controller.checkout(7L,checkoutBody()));
        assertEquals(0,count("order_info")); assertEquals(1000,jdbc.queryForObject("select stock from product",Integer.class)); assertEquals(2,qty());
    }
    @Test void additionAfterCheckoutSnapshotIsNotDeleted() throws Exception {
        row(2); gate.snapshot = new CountDownLatch(1); gate.release = new CountDownLatch(1); var pool = Executors.newFixedThreadPool(2);
        try {
            var checkout = pool.submit(() -> controller.checkout(7L,checkoutBody())); assertTrue(gate.snapshot.await(5,TimeUnit.SECONDS));
            var started = new CountDownLatch(1); var add = pool.submit(() -> { started.countDown(); controller.add(7L,addBody(3)); return true; }); assertTrue(started.await(5,TimeUnit.SECONDS));
            try { add.get(300,TimeUnit.MILLISECONDS); } catch (TimeoutException expected) { }
            gate.release.countDown(); assertEquals(0,checkout.get(15,TimeUnit.SECONDS).getCode()); assertTrue(add.get(15,TimeUnit.SECONDS));
            assertEquals(3,qty()); assertEquals(2,jdbc.queryForObject("select quantity from order_item",Integer.class));
        } finally { gate.release.countDown(); pool.shutdownNow(); }
    }
    @Test void zeroPriceAndExplicitBuyNowRemainValid() {
        jdbc.update("update product set price=0"); var body = checkoutBody(); var item = new CartController.CheckoutItemBody(); item.setProductId(1L); item.setQuantity(2); body.setItems(List.of(item));
        assertEquals(new BigDecimal("0.00"),controller.checkout(7L,body).getData().get("totalAmount")); assertEquals(1,count("order_info"));
    }

    @Test void concurrentAddsAtStockBoundaryAllowExactlyOneWinner() throws Exception {
        row(1); jdbc.update("update product set stock=3"); var pool = Executors.newFixedThreadPool(2); var start = new CyclicBarrier(2);
        try {
            java.util.concurrent.Callable<Boolean> add = () -> {
                start.await();
                try { controller.add(7L,addBody(2)); return true; }
                catch (BizException rejected) { assertEquals(2006,rejected.getCode()); return false; }
            };
            var a = pool.submit(add); var b = pool.submit(add);
            assertEquals(1,(a.get(15,TimeUnit.SECONDS) ? 1 : 0)+(b.get(15,TimeUnit.SECONDS) ? 1 : 0)); assertEquals(3,qty());
        } finally { pool.shutdownNow(); }
    }
    @Test void validUpdateRetainsBooleanCheckedContractAndHasNo99GlobalCap() {
        row(2); controller.update(7L,1L,Map.of("quantity",150,"checked",false)); assertEquals(150,qty());
        assertEquals(0,jdbc.queryForObject("select checked from cart_item",Integer.class));
        controller.update(7L,1L,Map.of("checked",true)); assertEquals(150,qty()); assertEquals(1,jdbc.queryForObject("select checked from cart_item",Integer.class));
    }
    @Test void updateCannotExceedStockOrMutateUnavailableProduct() {
        row(2); jdbc.update("update product set stock=3"); assertThrows(BizException.class,() -> controller.update(7L,1L,Map.of("quantity",4)));
        jdbc.update("update product set status='OFF_SALE'"); assertThrows(BizException.class,() -> controller.update(7L,1L,Map.of("quantity",1))); assertEquals(2,qty());
    }
    @Test void checkedCartDoubleCheckoutOnlyOrdersOneSnapshot() throws Exception {
        row(2); var pool = Executors.newFixedThreadPool(2); var start = new CyclicBarrier(2);
        try {
            java.util.concurrent.Callable<Boolean> checkout = () -> { start.await();
                try { controller.checkout(7L,checkoutBody()); return true; }
                catch (BizException empty) { assertEquals(2001,empty.getCode()); return false; }
            };
            var a = pool.submit(checkout); var b = pool.submit(checkout);
            assertEquals(1,(a.get(15,TimeUnit.SECONDS) ? 1 : 0)+(b.get(15,TimeUnit.SECONDS) ? 1 : 0)); assertEquals(1,count("order_info")); assertEquals(0,count("cart_item"));
        } finally { pool.shutdownNow(); }
    }
    private CartController.CheckoutBody explicit(int quantity) {
        var b = checkoutBody(); var item = new CartController.CheckoutItemBody(); item.setProductId(1L); item.setQuantity(quantity); b.setItems(List.of(item)); return b;
    }
    @Test void explicitPartialQuantityPreservesExistingWholeMatchingRowCleanupPolicy() {
        row(5); controller.checkout(7L,explicit(2)); assertEquals(0,count("cart_item")); assertEquals(2,jdbc.queryForObject("select quantity from order_item",Integer.class));
    }
    @Test void explicitRepeatWithoutKeyIsNotNewlyForbidden() {
        controller.checkout(7L,explicit(2)); controller.checkout(7L,explicit(2)); assertEquals(2,count("order_info"));
    }
    @Test void explicitBuyNowDoesNotDeleteCartRowInsertedAfterEmptySnapshot() throws Exception {
        gate.snapshot = new CountDownLatch(1); gate.release = new CountDownLatch(1); var pool = Executors.newSingleThreadExecutor();
        try {
            var checkout = pool.submit(() -> controller.checkout(7L,explicit(2))); assertTrue(gate.snapshot.await(5,TimeUnit.SECONDS));
            controller.add(7L,addBody(3)); gate.release.countDown(); assertEquals(0,checkout.get(15,TimeUnit.SECONDS).getCode()); assertEquals(3,qty());
        } finally { gate.release.countDown(); pool.shutdownNow(); }
    }
}
