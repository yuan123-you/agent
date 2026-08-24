package com.aimall.backend.migration;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertTrue;

class AgentBusinessActionMigrationContractTest {
    @Test
    void migrationAddsTargetOrderAndAfterSaleAggregate() throws Exception {
        var migration = new ClassPathResource("db/migration/V6__agent_business_actions.sql");
        assertTrue(migration.exists());
        String sql = new String(migration.getInputStream().readAllBytes(), StandardCharsets.UTF_8).toLowerCase();
        assertTrue(sql.contains("target_order_id"));
        assertTrue(sql.contains("create table after_sale"));
        assertTrue(sql.contains("unique key uk_after_sale_action"));
        assertTrue(sql.contains("order_item_id"));
    }
}
