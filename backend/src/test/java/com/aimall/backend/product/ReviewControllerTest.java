package com.aimall.backend.product;

import com.aimall.backend.common.BizException;
import com.aimall.backend.common.GlobalExceptionHandler;
import com.aimall.backend.config.MybatisPlusConfig;
import com.aimall.backend.entity.*;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.mapper.ProductReviewMapper;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.config.GlobalConfig;
import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.spring.MybatisSqlSessionFactoryBean;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.lang.reflect.Modifier;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;
import javax.sql.DataSource;
import org.apache.ibatis.executor.Executor;
import org.apache.ibatis.mapping.MappedStatement;
import org.apache.ibatis.plugin.*;
import org.apache.ibatis.session.ResultHandler;
import org.apache.ibatis.session.RowBounds;
import org.apache.ibatis.session.SqlSessionFactory;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;
import org.mybatis.spring.mapper.MapperFactoryBean;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import org.springframework.core.MethodParameter;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

public class ReviewControllerTest {
    // All mapper calls execute real SQL against a fresh, local-only database; no application config is loaded.
    @Intercepts(@Signature(type = Executor.class, method = "query", args = {
            MappedStatement.class, Object.class, RowBounds.class, ResultHandler.class}))
    public static class SqlTrace implements Interceptor {
        final List<String> queries = new CopyOnWriteArrayList<>();
        final List<Boolean> transactional = new CopyOnWriteArrayList<>();
        volatile Consumer<String> afterQuery = id -> {};
        volatile Runnable beforeQuery = () -> {};
        @Override public Object intercept(Invocation invocation) throws Throwable {
            MappedStatement statement = (MappedStatement) invocation.getArgs()[0];
            queries.add(statement.getBoundSql(invocation.getArgs()[1]).getSql().replaceAll("\\s+", " ").trim());
            transactional.add(TransactionSynchronizationManager.isActualTransactionActive());
            beforeQuery.run();
            Object result = invocation.proceed();
            afterQuery.accept(statement.getId());
            return result;
        }
    }

    @Configuration
    @EnableTransactionManagement(proxyTargetClass = true)
    @Import({MybatisPlusConfig.class, ReviewController.class})
    static class Config {
        @Bean Clock clock() { return Clock.systemUTC(); }
        @Bean DataSource dataSource() {
            return new DriverManagerDataSource("jdbc:h2:mem:reviews_" + UUID.randomUUID()
                    + ";MODE=MySQL;DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=10000", "sa", "");
        }
        @Bean JdbcTemplate jdbc(DataSource source) { return new JdbcTemplate(source); }
        @Bean PlatformTransactionManager transactionManager(DataSource source) { return new DataSourceTransactionManager(source); }
        @Bean SqlTrace sqlTrace() { return new SqlTrace(); }
        @Bean SqlSessionFactory sqlSessionFactory(DataSource source, MybatisPlusInterceptor interceptor,
                                                  MetaObjectHandler handler, SqlTrace trace) throws Exception {
            MybatisSqlSessionFactoryBean factory = new MybatisSqlSessionFactoryBean();
            factory.setDataSource(source);
            MybatisConfiguration configuration = new MybatisConfiguration();
            configuration.setMapUnderscoreToCamelCase(true);
            factory.setConfiguration(configuration);
            factory.setPlugins(interceptor, trace);
            factory.setGlobalConfig(new GlobalConfig().setMetaObjectHandler(handler));
            return factory.getObject();
        }
        @Bean MapperFactoryBean<ProductReviewMapper> reviews(SqlSessionFactory factory) {
            var mapper = new MapperFactoryBean<>(ProductReviewMapper.class); mapper.setSqlSessionFactory(factory); return mapper;
        }
        @Bean MapperFactoryBean<ProductMapper> products(SqlSessionFactory factory) {
            var mapper = new MapperFactoryBean<>(ProductMapper.class); mapper.setSqlSessionFactory(factory); return mapper;
        }
        @Bean MapperFactoryBean<UserMapper> users(SqlSessionFactory factory) {
            var mapper = new MapperFactoryBean<>(UserMapper.class); mapper.setSqlSessionFactory(factory); return mapper;
        }
    }

    public static class SqlFixture implements AutoCloseable {
        public final AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext(Config.class);
        public final JdbcTemplate jdbc = context.getBean(JdbcTemplate.class);
        final ReviewController controller = context.getBean(ReviewController.class);
        final SqlTrace trace = context.getBean(SqlTrace.class);
        public SqlFixture() {
            createTable("product", Product.class);
            createTable("product_review", ProductReview.class);
            createTable("sys_user", User.class);
            createTable("order_info", OrderInfo.class);
            createTable("order_item", OrderItem.class);
            jdbc.update("insert into sys_user(id,nickname,deleted) values(7,'Buyer',0),(8,'Other',0)");
            jdbc.update("insert into product(id,name,deleted) values(1,'Product',0),(2,'Other product',0)");
            jdbc.update("insert into order_info(id,user_id,status) values(30,7,'DELIVERED'),(31,8,'DELIVERED'),(32,7,'SHIPPED'),(33,7,'DELIVERED')");
            jdbc.update("insert into order_item(id,order_id,product_id) values(40,30,1),(41,31,1),(42,32,1),(43,30,2),(44,33,1)");
        }
        private void createTable(String name, Class<?> entity) {
            List<String> columns = new ArrayList<>();
            for (var field : entity.getDeclaredFields()) {
                if (Modifier.isStatic(field.getModifiers())) continue;
                String column = field.getName().replaceAll("([a-z0-9])([A-Z])", "$1_$2").toLowerCase(Locale.ROOT);
                if ("id".equals(column)) { columns.add("id bigint generated by default as identity primary key"); continue; }
                Class<?> type = field.getType();
                String sqlType = "spec_info".equals(column) ? "varchar(255)" : type == Long.class ? "bigint" : type == Integer.class ? "integer"
                        : type == Boolean.class ? "boolean" : type == BigDecimal.class ? "decimal(18,2)"
                        : type == LocalDateTime.class ? "timestamp" : "varchar(4096)";
                columns.add(column + " " + sqlType + ("deleted".equals(column) ? " default 0" : ""));
            }
            jdbc.execute("create table " + name + "(" + String.join(",", columns) + ")");
        }
        void review(long userId, int rating, int deleted) {
            jdbc.update("insert into product_review(product_id,user_id,rating,content,deleted) values(1,?,?, 'Historical',?)", userId, rating, deleted);
        }
        @Override public void close() { jdbc.execute("drop all objects"); context.close(); }
    }

    static ReviewController.CreateBody body(Long orderItemId) throws Exception {
        return new ObjectMapper().readValue(
                "{\"rating\":4,\"content\":\"Good purchase\",\"specInfo\":\"Blue\""
                        + (orderItemId == null ? "" : ",\"orderItemId\":" + orderItemId) + "}", ReviewController.CreateBody.class);
    }

    private SqlFixture db;
    @BeforeEach void setUp() { db = new SqlFixture(); }
    @AfterEach void tearDown() { db.close(); }

    @Test void unpurchasedProductCannotBeReviewed() throws Exception {
        db.jdbc.update("delete from order_item where product_id=1 and order_id in (30,33)");
        var body = body(null);
        assertThrows(BizException.class, () -> db.controller.create(7L, 1L, body));
        assertEquals(0, db.jdbc.queryForObject("select count(*) from product_review", Integer.class));
    }

    @ParameterizedTest @ValueSource(longs = {41, 42, 43, 999, 0, -1})
    void explicitItemMustBeOwnedDeliveredAndMatchProduct(long itemId) throws Exception {
        var body = body(itemId);
        assertThrows(BizException.class, () -> db.controller.create(7L, 1L, body));
        assertEquals(0, db.jdbc.queryForObject("select count(*) from product_review", Integer.class));
    }

    @ParameterizedTest @NullSource @ValueSource(longs = {40, 44})
    void deliveredPurchaseIsPersistedOnReview(Long itemId) throws Exception {
        assertEquals(0, db.controller.create(7L, 1L, body(itemId)).getCode());
        Long saved = db.jdbc.queryForObject("select order_item_id from product_review", Long.class);
        assertNotNull(saved, "review must reference a verified purchase");
        if (itemId != null) assertEquals(itemId, saved);
        else assertTrue(Set.of(40L, 44L).contains(saved), "implicit purchase must resolve to a delivered item");
    }

    @ParameterizedTest @ValueSource(strings = {"PENDING_PAYMENT", "PAID", "SHIPPED", "CANCELLED"})
    void implicitPurchaseMustBeDelivered(String status) throws Exception {
        db.jdbc.update("update order_info set status=? where user_id=7", status);
        var body = body(null);
        assertThrows(BizException.class, () -> db.controller.create(7L, 1L, body));
    }

    @Test void oldReviewWithoutOrderItemStillPreventsAnotherReviewAcrossOrders() throws Exception {
        db.review(7, 5, 0);
        var body = body(44L);
        assertThrows(BizException.class, () -> db.controller.create(7L, 1L, body));
        assertEquals(1, db.jdbc.queryForObject("select count(*) from product_review where deleted=0", Integer.class));
    }

    @Test void historicalDuplicatesDoNotRequireSchemaCleanupAndStillBlockNewReview() throws Exception {
        db.review(7, 4, 0); db.review(7, 5, 0);
        var body = body(null);
        assertThrows(BizException.class, () -> db.controller.create(7L, 1L, body));
        assertEquals(2, db.jdbc.queryForObject("select count(*) from product_review where deleted=0", Integer.class));
    }

    @Test void logicallyDeletedReviewDoesNotBlockNewReview() throws Exception {
        db.review(7, 1, 1);
        assertEquals(0, db.controller.create(7L, 1L, body(40L)).getCode());
        assertEquals(1, db.jdbc.queryForObject("select count(*) from product_review where deleted=0", Integer.class));
    }

    @ParameterizedTest @NullSource @ValueSource(longs = {999})
    void missingAuthenticatedUserCannotCreateReview(Long userId) throws Exception {
        var body = body(null);
        assertThrows(BizException.class, () -> db.controller.create(userId, 1L, body));
    }

    @Test void missingProductCannotCreateReview() throws Exception {
        var body = body(null);
        assertThrows(BizException.class, () -> db.controller.create(7L, 999L, body));
    }

    @ParameterizedTest @CsvSource({"0,20", "-1,20", "1,0", "1,-1", "1,101", "9223372036854775807,20"})
    void invalidPaginationIsRejectedBeforeSql(long page, long size) {
        assertThrows(BizException.class, () -> db.controller.list(1L, page, size));
        assertTrue(db.trace.queries.isEmpty(), "invalid pagination must not reach SQL");
    }

    @Test void statisticsCoverAllActiveReviewsButNeverLoadAllReviewEntities() {
        db.review(7, 5, 0); db.review(8, 2, 0); db.review(7, 1, 1);
        var data = db.controller.list(1L, 1, 1).getData();
        assertEquals(2L, data.get("total"));
        assertEquals(3.5, data.get("avgRating"));
        assertEquals(Map.of("1", 0L, "2", 1L, "3", 0L, "4", 0L, "5", 1L), data.get("ratingDistribution"));
        var records = (List<?>) data.get("records");
        assertEquals(1, records.size());
        assertEquals(2, ((Map<?, ?>) records.get(0)).get("rating"));
        assertTrue(db.trace.queries.stream().filter(sql -> sql.toLowerCase(Locale.ROOT).contains("from product_review"))
                .noneMatch(sql -> !sql.toLowerCase(Locale.ROOT).contains("limit")
                        && !sql.toLowerCase(Locale.ROOT).contains("count(")), "statistics must use SQL aggregation, not entity scans");
    }

    @Test void oversizedSpecInfoIsBadRequestBeforeAnySql() throws Exception {
        postReviewWithSpecInfo("s".repeat(256)).andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(2001));
        assertTrue(db.trace.queries.isEmpty(), "request validation must reject the oversized database field before the transaction");
        assertEquals(0, db.jdbc.queryForObject("select count(*) from product_review", Integer.class));
    }

    @Test void specInfoAtColumnLimitIsAccepted() throws Exception {
        String spec = "s".repeat(255);
        postReviewWithSpecInfo(spec).andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0));
        assertEquals(spec, db.jdbc.queryForObject("select spec_info from product_review", String.class));
    }

    private ResultActions postReviewWithSpecInfo(String spec) throws Exception {
        var mvc = MockMvcBuilders.standaloneSetup(db.controller).setControllerAdvice(new GlobalExceptionHandler())
                .setCustomArgumentResolvers(new HandlerMethodArgumentResolver() {
                    @Override public boolean supportsParameter(MethodParameter parameter) {
                        return parameter.hasParameterAnnotation(AuthenticationPrincipal.class);
                    }
                    @Override public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer container,
                                                             NativeWebRequest request, WebDataBinderFactory factory) {
                        return 7L;
                    }
                }).build();
        String json = new ObjectMapper().writeValueAsString(Map.of("rating", 4, "content", "Good purchase",
                "orderItemId", 40L, "specInfo", spec));
        return mvc.perform(post("/api/v1/products/1/reviews").contentType(MediaType.APPLICATION_JSON).content(json));
    }
    @Test void zeroAffectedRowsMustNotReturnSuccess() throws Exception {
        var mapper = org.mockito.Mockito.mock(ProductReviewMapper.class,
                org.mockito.AdditionalAnswers.delegatesTo(db.context.getBean(ProductReviewMapper.class)));
        org.mockito.Mockito.doReturn(0).when(mapper).insert(org.mockito.ArgumentMatchers.any(ProductReview.class));
        var controller = new ReviewController(mapper, db.context.getBean(ProductMapper.class), db.context.getBean(UserMapper.class));
        var body = body(40L);
        assertThrows(BizException.class, () -> controller.create(7L, 1L, body));
        assertEquals(0, db.jdbc.queryForObject("select count(*) from product_review", Integer.class));
    }
    @Test void emptyReviewStatisticsKeepExistingResponseDefaults() {
        var data = db.controller.list(1L, 1, 100).getData();
        assertEquals(0L, data.get("total"));
        assertEquals(5.0, data.get("avgRating"));
        assertEquals(Map.of("1", 0L, "2", 0L, "3", 0L, "4", 0L, "5", 0L), data.get("ratingDistribution"));
    }
}
