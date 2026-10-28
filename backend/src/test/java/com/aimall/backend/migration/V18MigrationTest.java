package com.aimall.backend.migration;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

class V18MigrationTest {

    @Test
    void v18MigrationRestoresPhonesAndUpdatesAccessories() throws IOException {
        ClassPathResource migration = new ClassPathResource("db/migration/V18__restore_phones_and_fix_accessory_categories.sql");
        assertThat(migration.exists()).isTrue();

        String sql;
        try (InputStream input = migration.getInputStream()) {
            sql = new String(input.readAllBytes(), StandardCharsets.UTF_8).toLowerCase(Locale.ROOT);
        }

        // 验证确保包含 DIGITAL 分类
        assertThat(sql).contains("digital");
        assertThat(sql).contains("mall_category");

        // 验证将配件分类从 PHONE 调整为 DIGITAL
        assertThat(sql).contains("set category = 'digital'");
        assertThat(sql).contains("where category = 'phone'");
        assertThat(sql).contains("%卡包%");
        assertThat(sql).contains("%耳机%");
        assertThat(sql).contains("%钥匙扣%");

        // 验证恢复手机商品上架
        assertThat(sql).contains("status = 'on_sale'");
        assertThat(sql).contains("where id between 1 and 9");
    }
}
