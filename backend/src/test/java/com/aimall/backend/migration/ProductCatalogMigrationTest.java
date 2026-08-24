package com.aimall.backend.migration;

import static org.assertj.core.api.Assertions.assertThat;

import com.aimall.backend.entity.Product;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.Locale;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

class ProductCatalogMigrationTest {

    @Test
    void migrationAddsCatalogProvenanceWithoutChangingBaselineColumns() throws IOException {
        ClassPathResource migration = new ClassPathResource("db/migration/V6__product_catalog_provenance.sql");
        assertThat(migration.exists()).isTrue();

        String sql;
        try (InputStream input = migration.getInputStream()) {
            sql = new String(input.readAllBytes(), StandardCharsets.UTF_8).toLowerCase(Locale.ROOT);
        }

        assertThat(sql).contains("currency varchar(16) null");
        assertThat(sql).contains("source_name varchar(255) null");
        assertThat(sql).contains("source_url varchar(2048) null");
        assertThat(sql).contains("source_product_id varchar(255) null");
        assertThat(sql).contains("source_updated_at datetime(3) null");
        assertThat(sql).contains("collected_at datetime(3) null");
        assertThat(sql).contains("original_image_url varchar(2048) null");
        assertThat(sql).contains("image_sha256 char(64) null");
        assertThat(sql).contains("simulated_commerce_fields tinyint not null default 0");
        assertThat(sql).contains("modify column image_url varchar(512) null");
        assertThat(sql).contains("unique key uk_product_source (source_name, source_product_id)");
        assertThat(sql).contains("key idx_product_collected_status (collected_at, status)");
        assertThat(Pattern.compile("unique\\s+key\\s+uk_product_source\\s*\\(\\s*source_name\\s*,\\s*source_product_id\\s*\\)")
                .matcher(sql).find()).isTrue();
    }

    @Test
    void productMapsCatalogProvenanceFields() throws NoSuchFieldException {
        assertField("currency", String.class);
        assertField("sourceName", String.class);
        assertField("sourceUrl", String.class);
        assertField("sourceProductId", String.class);
        assertField("sourceUpdatedAt", LocalDateTime.class);
        assertField("collectedAt", LocalDateTime.class);
        assertField("originalImageUrl", String.class);
        assertField("imageSha256", String.class);
        assertField("simulatedCommerceFields", Boolean.class);
    }

    private void assertField(String name, Class<?> type) throws NoSuchFieldException {
        Field field = Product.class.getDeclaredField(name);
        assertThat(field.getType()).isEqualTo(type);
    }
}