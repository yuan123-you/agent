package com.aimall.backend.internal;

import com.aimall.backend.chat.AiClient;
import com.aimall.backend.common.BizException;
import com.aimall.backend.config.MybatisPlusConfig;
import com.aimall.backend.config.ObjectStorage;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.kb.KbService;
import com.aimall.backend.mapper.KbChunkMapper;
import com.aimall.backend.mapper.KbDocMapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.config.GlobalConfig;
import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.spring.MybatisSqlSessionFactoryBean;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.ibatis.session.SqlSessionFactory;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mybatis.spring.mapper.MapperFactoryBean;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

import javax.sql.DataSource;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.time.Clock;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class InternalKbIngestTransactionTest {
    static class Gate {
        final AtomicBoolean pauseRead = new AtomicBoolean();
        final AtomicBoolean pauseInsert = new AtomicBoolean();
        final CountDownLatch reached = new CountDownLatch(1);
        final CountDownLatch release = new CountDownLatch(1);
        void pause() throws InterruptedException {
            reached.countDown();
            if (!release.await(10, TimeUnit.SECONDS)) throw new AssertionError("gate timeout");
        }
    }

    @Configuration
    @EnableTransactionManagement(proxyTargetClass = true)
    @Import(MybatisPlusConfig.class)
    static class Config {
        @Bean Clock clock() { return Clock.systemDefaultZone(); }
        @Bean Gate gate() { return new Gate(); }
        @Bean DataSource dataSource() {
            return new DriverManagerDataSource("jdbc:h2:mem:kb_" + UUID.randomUUID()
                    + ";MODE=MySQL;DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=10000", "sa", "");
        }
        @Bean JdbcTemplate jdbc(DataSource ds) { return new JdbcTemplate(ds); }
        @Bean PlatformTransactionManager transactionManager(DataSource ds) {
            return new DataSourceTransactionManager(ds);
        }
        @Bean SqlSessionFactory sqlSessionFactory(DataSource ds, MybatisPlusInterceptor interceptor,
                                                  MetaObjectHandler handler) throws Exception {
            var factory = new MybatisSqlSessionFactoryBean();
            factory.setDataSource(ds);
            var config = new MybatisConfiguration();
            config.setMapUnderscoreToCamelCase(true);
            factory.setConfiguration(config);
            factory.setPlugins(interceptor);
            factory.setGlobalConfig(new GlobalConfig().setMetaObjectHandler(handler));
            return factory.getObject();
        }
        @Bean MapperFactoryBean<KbDocMapper> docs(SqlSessionFactory factory) {
            var bean = new MapperFactoryBean<>(KbDocMapper.class);
            bean.setSqlSessionFactory(factory);
            return bean;
        }
        @Bean MapperFactoryBean<KbChunkMapper> chunks(SqlSessionFactory factory) {
            var bean = new MapperFactoryBean<>(KbChunkMapper.class);
            bean.setSqlSessionFactory(factory);
            return bean;
        }
        @Bean AiClient aiClient() {
            AiClient client = mock(AiClient.class);
            when(client.triggerIngest(anyMap())).thenReturn(Mono.empty());
            when(client.deleteVectors(anyLong(), anyInt())).thenReturn(Mono.empty());
            return client;
        }
        @Bean InternalKbController controller(KbDocMapper docs, KbChunkMapper chunks, Gate gate) {
            return new InternalKbController(observe(KbDocMapper.class, docs, gate),
                    observe(KbChunkMapper.class, chunks, gate), mock(Bm25Retriever.class));
        }
        @Bean KbService service(KbDocMapper docs, KbChunkMapper chunks, AiClient ai, Gate gate) {
            return new KbService(observe(KbDocMapper.class, docs, gate), chunks, ai, mock(ObjectStorage.class));
        }
        private static <T> T observe(Class<T> type, T delegate, Gate gate) {
            return type.cast(Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type},
                    (proxy, method, args) -> {
                        Object result;
                        try { result = method.invoke(delegate, args); }
                        catch (InvocationTargetException ex) { throw ex.getCause(); }
                        if ((method.getName().equals("selectById") || method.getName().equals("selectForUpdate")
                                || method.getName().equals("selectOne")) && gate.pauseRead.getAndSet(false)) {
                            gate.pause();
                        }
                        if (type == KbChunkMapper.class && method.getName().equals("insert")
                                && gate.pauseInsert.getAndSet(false)) gate.pause();
                        return result;
                    }));
        }
    }

    private AnnotationConfigApplicationContext context;
    private JdbcTemplate jdbc;
    private InternalKbController controller;
    private KbService service;
    private AiClient ai;
    private Gate gate;
    private final ObjectMapper json = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

    @BeforeEach void setup() {
        context = new AnnotationConfigApplicationContext(Config.class);
        jdbc = context.getBean(JdbcTemplate.class);
        controller = context.getBean(InternalKbController.class);
        service = context.getBean(KbService.class);
        ai = context.getBean(AiClient.class);
        gate = context.getBean(Gate.class);
        jdbc.execute("CREATE TABLE kb_doc (id BIGINT PRIMARY KEY, product_id BIGINT, title VARCHAR(128),"
                + "doc_type VARCHAR(16), file_url VARCHAR(255), file_format VARCHAR(16), status VARCHAR(16),"
                + "chunk_count INT DEFAULT 0, vector_count INT DEFAULT 0, fail_reason VARCHAR(255),"
                + "version INT, created_by BIGINT, created_at TIMESTAMP, updated_at TIMESTAMP, deleted INT DEFAULT 0)");
        jdbc.execute("CREATE TABLE kb_chunk (id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,"
                + "doc_id BIGINT, product_id BIGINT, doc_type VARCHAR(16), doc_version INT, chunk_index INT,"
                + "content VARCHAR(4000) NOT NULL, token_count INT, created_at TIMESTAMP)");
        jdbc.update("INSERT INTO kb_doc(id,title,doc_type,file_url,file_format,status,version,updated_at)"
                + " VALUES(7,?,'POLICY','seed.md','MD','PROCESSING',2,?)",
                KbService.SEED_POLICY_TITLE, LocalDateTime.now().minusMinutes(5));
        jdbc.update("INSERT INTO kb_chunk(doc_id,doc_version,chunk_index,content) VALUES(7,1,0,'old'),(7,2,0,'current')");
    }
    @AfterEach void cleanup() { gate.release.countDown(); context.close(); }

    private InternalKbController.ChunksBatchBody batch(Integer version) throws Exception {
        return json.readValue("{\"docId\":7,\"docVersion\":" + version
                + ",\"chunks\":[{\"chunkIndex\":1,\"content\":\"new\"}]}",
                InternalKbController.ChunksBatchBody.class);
    }
    private InternalKbController.ResultBody result(Integer version, String status) throws Exception {
        return json.readValue("{\"docId\":7,\"docVersion\":" + version + ",\"status\":\"" + status
                + "\",\"chunkCount\":8,\"vectorCount\":5,\"failReason\":\"callback\"}",
                InternalKbController.ResultBody.class);
    }
    private String status() { return jdbc.queryForObject("SELECT status FROM kb_doc WHERE id=7", String.class); }
    private int version() { return jdbc.queryForObject("SELECT version FROM kb_doc WHERE id=7", Integer.class); }
    private int chunkCount() { return jdbc.queryForObject("SELECT COUNT(*) FROM kb_chunk", Integer.class); }

    @ParameterizedTest @ValueSource(strings = {"DISABLED", "ACTIVE", "FAILED", "PENDING"})
    void nonProcessingDocumentRejectsChunksAndResults(String status) throws Exception {
        jdbc.update("UPDATE kb_doc SET status=? WHERE id=7", status);
        var batch = batch(2);
        var active = result(2, "ACTIVE");
        var failed = result(2, "FAILED");
        assertThrows(BizException.class, () -> controller.chunksBatch(batch));
        assertThrows(BizException.class, () -> controller.result(active));
        assertThrows(BizException.class, () -> controller.result(failed));
        assertEquals(status, status());
        assertEquals(2, chunkCount());
    }

    @ParameterizedTest @ValueSource(ints = {1, 3})
    void mismatchedTaskCannotInsertOrPruneCurrentChunksOrChangeMetadata(int taskVersion) throws Exception {
        var batch = batch(taskVersion);
        var active = result(taskVersion, "ACTIVE");
        var failed = result(taskVersion, "FAILED");
        assertThrows(BizException.class, () -> controller.chunksBatch(batch));
        assertThrows(BizException.class, () -> controller.result(active));
        assertThrows(BizException.class, () -> controller.result(failed));
        assertEquals("PROCESSING", status());
        assertEquals(2, chunkCount());
        assertEquals(0, jdbc.queryForObject("SELECT chunk_count FROM kb_doc WHERE id=7", Integer.class));
        assertNull(jdbc.queryForObject("SELECT fail_reason FROM kb_doc WHERE id=7", String.class));
    }

    @Test void missingVersionFailsClosed() throws Exception {
        var batch = batch(null);
        var result = result(null, "ACTIVE");
        assertThrows(BizException.class, () -> controller.chunksBatch(batch));
        assertThrows(BizException.class, () -> controller.result(result));
        assertEquals("PROCESSING", status());
    }

    @ParameterizedTest @ValueSource(strings = {"PROCESSING", "DISABLED", "PENDING", "unknown"})
    void callbackOnlyAcceptsTerminalIngestStatuses(String status) throws Exception {
        var body = result(2, status);
        assertThrows(BizException.class, () -> controller.result(body));
        assertEquals("PROCESSING", status());
    }

    @Test void matchingTaskWritesItsVersionAndActivePrunesOnlySupersededChunks() throws Exception {
        var ids = controller.chunksBatch(batch(2)).getData().get("ids");
        assertEquals(1, ((List<?>) ids).size());
        assertEquals(2, jdbc.queryForObject("SELECT doc_version FROM kb_chunk WHERE content='new'", Integer.class));
        controller.result(result(2, "ACTIVE"));
        assertEquals("ACTIVE", status());
        assertEquals(2, chunkCount());
        assertEquals(8, jdbc.queryForObject("SELECT chunk_count FROM kb_doc WHERE id=7", Integer.class));
        assertEquals(5, jdbc.queryForObject("SELECT vector_count FROM kb_doc WHERE id=7", Integer.class));
    }

    @Test void matchingFailureDoesNotPruneChunks() throws Exception {
        controller.result(result(2, "FAILED"));
        assertEquals("FAILED", status());
        assertEquals(2, chunkCount());
        assertEquals("callback", jdbc.queryForObject("SELECT fail_reason FROM kb_doc WHERE id=7", String.class));
    }

    @Test void versionAliasIsBoundToTheTask() throws Exception {
        var body = json.readValue("{\"docId\":7,\"version\":1,\"status\":\"ACTIVE\"}",
                InternalKbController.ResultBody.class);
        assertThrows(BizException.class, () -> controller.result(body));
        var current = json.readValue("{\"docId\":7,\"version\":2,\"status\":\"ACTIVE\"}",
                InternalKbController.ResultBody.class);
        controller.result(current);
        assertEquals("ACTIVE", status());
    }

    @Test void batchInsertFailureRollsBackEveryChunk() throws Exception {
        var body = batch(2);
        var invalid = new InternalKbController.ChunkItem();
        invalid.setChunkIndex(2);
        body.setChunks(List.of(body.getChunks().get(0), invalid));
        assertThrows(RuntimeException.class, () -> controller.chunksBatch(body));
        assertEquals(2, chunkCount(), "first insert must roll back with the invalid second chunk");
    }

    @Test void reindexWaitsUntilTheWholeBatchCommits() throws Exception {
        var body = batch(2);
        gate.pauseInsert.set(true);
        var executor = Executors.newFixedThreadPool(2);
        try {
            var callback = executor.submit(() -> controller.chunksBatch(body));
            assertTrue(gate.reached.await(5, TimeUnit.SECONDS));
            var reindex = executor.submit(() -> service.reindex(7L));
            assertThrows(TimeoutException.class, () -> reindex.get(250, TimeUnit.MILLISECONDS));
            gate.release.countDown();
            callback.get(5, TimeUnit.SECONDS);
            reindex.get(5, TimeUnit.SECONDS);
            assertEquals(3, version());
            assertEquals("PROCESSING", status());
            assertEquals(2, jdbc.queryForObject("SELECT doc_version FROM kb_chunk WHERE content='new'", Integer.class));
        } finally { gate.release.countDown(); executor.shutdownNow(); }
    }

    @Test void disableCannotBeOverwrittenByAResultAlreadyReadingTheDocument() throws Exception {
        var body = result(2, "ACTIVE");
        gate.pauseRead.set(true);
        var executor = Executors.newFixedThreadPool(2);
        try {
            var callback = executor.submit(() -> controller.result(body));
            assertTrue(gate.reached.await(5, TimeUnit.SECONDS));
            var disable = executor.submit(() -> service.toggleStatus(7L, "DISABLED"));
            assertThrows(TimeoutException.class, () -> disable.get(250, TimeUnit.MILLISECONDS));
            gate.release.countDown();
            callback.get(5, TimeUnit.SECONDS);
            disable.get(5, TimeUnit.SECONDS);
            assertEquals("DISABLED", status());
        } finally { gate.release.countDown(); executor.shutdownNow(); }
    }

    @Test void startupAndRetryNeverReviveDisabledPolicy() {
        jdbc.update("UPDATE kb_doc SET status='DISABLED' WHERE id=7");
        service.seedPolicyIfNeeded();
        service.seedPolicyRetry();
        assertEquals("DISABLED", status());
        verify(ai, never()).triggerIngest(anyMap());
    }

    @Test void startupDoesNotRedispatchFreshProcessingPolicy() {
        jdbc.update("UPDATE kb_doc SET updated_at=? WHERE id=7", LocalDateTime.now());
        service.seedPolicyIfNeeded();
        assertEquals(2, version());
        verify(ai, never()).triggerIngest(anyMap());
    }

    @ParameterizedTest @ValueSource(strings = {"FAILED", "PROCESSING"})
    void retryGetsANewVersionThatRejectsThePreviousAttempt(String state) throws Exception {
        jdbc.update("UPDATE kb_doc SET status=? WHERE id=7", state);
        service.seedPolicyRetry();
        assertEquals(3, version());
        assertEquals("PROCESSING", status());
        var old = result(2, "ACTIVE");
        assertThrows(BizException.class, () -> controller.result(old));
        verify(ai).triggerIngest(argThat(body -> Integer.valueOf(3).equals(body.get("doc_version"))));
    }

    @Test void seedClaimCannotRevivePolicyDisabledAfterItsRead() throws Exception {
        jdbc.update("UPDATE kb_doc SET status='FAILED' WHERE id=7");
        gate.pauseRead.set(true);
        var executor = Executors.newSingleThreadExecutor();
        try {
            var retry = executor.submit(() -> service.seedPolicyRetry());
            assertTrue(gate.reached.await(5, TimeUnit.SECONDS));
            service.toggleStatus(7L, "DISABLED");
            gate.release.countDown();
            retry.get(5, TimeUnit.SECONDS);
            assertEquals("DISABLED", status());
            verify(ai, never()).triggerIngest(anyMap());
        } finally { gate.release.countDown(); executor.shutdownNow(); }
    }

    @Test void generatedSeedDispatchCannotReviveDisabledSnapshot() {
        KbDoc snapshot = context.getBean(KbDocMapper.class).selectById(7L);
        service.toggleStatus(7L, "DISABLED");
        service.dispatchSeedDocument(snapshot);
        assertEquals("DISABLED", status());
        verify(ai, never()).triggerIngest(anyMap());
    }

    @Test void reindexCannotOverwriteADisableAfterItsRead() throws Exception {
        gate.pauseRead.set(true);
        var executor = Executors.newSingleThreadExecutor();
        try {
            var reindex = executor.submit(() -> service.reindex(7L));
            assertTrue(gate.reached.await(5, TimeUnit.SECONDS));
            service.toggleStatus(7L, "DISABLED");
            gate.release.countDown();
            try { reindex.get(5, TimeUnit.SECONDS); }
            catch (ExecutionException ex) { assertInstanceOf(BizException.class, ex.getCause()); }
            assertEquals("DISABLED", status());
            verify(ai, never()).triggerIngest(anyMap());
        } finally { gate.release.countDown(); executor.shutdownNow(); }
    }

    @Test void concurrentReindexesFromTheSameSnapshotOnlyDispatchOneNewVersion() throws Exception {
        gate.pauseRead.set(true);
        var executor = Executors.newSingleThreadExecutor();
        try {
            var first = executor.submit(() -> service.reindex(7L));
            assertTrue(gate.reached.await(5, TimeUnit.SECONDS));
            service.reindex(7L);
            gate.release.countDown();
            ExecutionException conflict = assertThrows(ExecutionException.class,
                    () -> first.get(5, TimeUnit.SECONDS));
            assertInstanceOf(BizException.class, conflict.getCause());
            assertEquals(3, version());
            verify(ai, times(1)).triggerIngest(argThat(body -> Integer.valueOf(3).equals(body.get("doc_version"))));
        } finally { gate.release.countDown(); executor.shutdownNow(); }
    }

    @Test void concurrentSeedRetriesOnlyDispatchTheClaimWinner() throws Exception {
        jdbc.update("UPDATE kb_doc SET status='FAILED' WHERE id=7");
        gate.pauseRead.set(true);
        var executor = Executors.newSingleThreadExecutor();
        try {
            var first = executor.submit(() -> service.seedPolicyRetry());
            assertTrue(gate.reached.await(5, TimeUnit.SECONDS));
            service.seedPolicyRetry();
            gate.release.countDown();
            first.get(5, TimeUnit.SECONDS);
            assertEquals(3, version());
            verify(ai, times(1)).triggerIngest(anyMap());
        } finally { gate.release.countDown(); executor.shutdownNow(); }
    }

    @Test void pendingSeedStartsOnceWithoutChangingItsInitialVersion() {
        jdbc.update("UPDATE kb_doc SET status='PENDING',version=1 WHERE id=7");
        service.seedPolicyIfNeeded();
        service.seedPolicyIfNeeded();
        assertEquals("PROCESSING", status());
        assertEquals(1, version());
        verify(ai, times(1)).triggerIngest(argThat(body -> Integer.valueOf(1).equals(body.get("doc_version"))));
    }

    @Test void retryDoesNotDispatchFreshProcessingOrOldPendingPolicy() {
        jdbc.update("UPDATE kb_doc SET updated_at=? WHERE id=7", LocalDateTime.now());
        service.seedPolicyRetry();
        jdbc.update("UPDATE kb_doc SET status='PENDING',updated_at=? WHERE id=7", LocalDateTime.now().minusDays(1));
        service.seedPolicyRetry();
        assertEquals("PENDING", status());
        assertEquals(2, version());
        verify(ai, never()).triggerIngest(anyMap());
    }

    @Test void lateDispatchFailureCannotOverwriteDisabledOrANewerVersion() {
        Sinks.One<Void> failure = Sinks.one();
        when(ai.triggerIngest(anyMap())).thenReturn(failure.asMono());
        service.triggerIngest(context.getBean(KbDocMapper.class).selectById(7L));
        service.toggleStatus(7L, "DISABLED");
        failure.tryEmitError(new IllegalStateException("offline"));
        assertEquals("DISABLED", status());

        Sinks.One<Void> oldFailure = Sinks.one();
        when(ai.triggerIngest(anyMap())).thenReturn(oldFailure.asMono(), Mono.empty());
        jdbc.update("UPDATE kb_doc SET status='PROCESSING' WHERE id=7");
        service.triggerIngest(context.getBean(KbDocMapper.class).selectById(7L));
        service.reindex(7L);
        oldFailure.tryEmitError(new IllegalStateException("old attempt offline"));
        assertEquals("PROCESSING", status());
        assertEquals(3, version());
    }
}
