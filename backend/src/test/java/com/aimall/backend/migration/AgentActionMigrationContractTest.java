package com.aimall.backend.migration;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import static org.junit.jupiter.api.Assertions.assertTrue;
class AgentActionMigrationContractTest {
    @Test void migrationCreatesAuditableAgentActionTable() throws IOException {
        ClassPathResource migration = new ClassPathResource("db/migration/V3__agent_action.sql");
        assertTrue(migration.exists(), "agent_action must be introduced through Flyway V3");
        try (InputStream input = migration.getInputStream()) {
            String sql = new String(input.readAllBytes(), StandardCharsets.UTF_8).toLowerCase();
            assertTrue(sql.contains("create table agent_action"));
            assertTrue(sql.contains("action_id")); assertTrue(sql.contains("payload"));
            assertTrue(sql.contains("expires_at")); assertTrue(sql.contains("order_id"));
        }
    }
}
