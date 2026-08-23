package com.aimall.backend.migration;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import static org.assertj.core.api.Assertions.assertThat;

class DashboardIndexMigrationContractTest {
    @Test
    void migrationAddsIndexesForDashboardPredicates() throws IOException {
        ClassPathResource migration = new ClassPathResource("db/migration/V5__dashboard_query_indexes.sql");
        assertThat(migration.exists()).isTrue();
        try (InputStream input = migration.getInputStream()) {
            String sql = new String(input.readAllBytes(), StandardCharsets.UTF_8).toLowerCase();
            assertThat(sql).contains("on order_info (created_at)");
            assertThat(sql).contains("on conversation (created_at, deleted)");
            assertThat(sql).contains("on product (status, deleted)");
        }
    }
}
