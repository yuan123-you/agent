package com.aimall.backend.migration;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.MutablePropertySources;
import org.springframework.core.env.PropertiesPropertySource;
import org.springframework.core.env.PropertySource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.io.ClassPathResource;

class FlywayMigrationContractTest {

    @Test
    void flywayRuntimeIsAvailable() throws ClassNotFoundException {
        assertNotNull(Class.forName("org.flywaydb.core.Flyway"));
    }

    @Test
    void legacyDatabasesAreAdoptedAtVersionTwo() throws IOException {
        StandardEnvironment environment = applicationEnvironment();

        assertEquals("true", environment.getProperty("spring.flyway.enabled"));
        assertEquals("classpath:db/migration", environment.getProperty("spring.flyway.locations"));
        assertEquals("true", environment.getProperty("spring.flyway.baseline-on-migrate"));
        assertEquals("2", environment.getProperty("spring.flyway.baseline-version"));
        assertEquals("true", environment.getProperty("spring.flyway.validate-on-migrate"));
    }

    @Test
    void baselineCreatesTheCurrentFourteenTableSchema() throws IOException {
        ClassPathResource migration = new ClassPathResource("db/migration/V1__baseline.sql");
        assertTrue(migration.exists(), "V1 Flyway baseline must exist");

        String sql;
        try (InputStream input = migration.getInputStream()) {
            sql = new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }

        Matcher tables = Pattern.compile("(?im)^CREATE\\s+TABLE\\s+`?[a-z_]+`?\\s*\\(").matcher(sql);
        int tableCount = 0;
        while (tables.find()) {
            tableCount++;
        }

        assertEquals(14, tableCount);
        assertFalse(Pattern.compile("(?im)^\\s*(CREATE\\s+DATABASE|USE\\s+)").matcher(sql).find(),
                "Flyway must migrate the configured datasource database only");
    }

    @Test
    void structuredAddressMigrationAddsRegionColumns() throws IOException {
        ClassPathResource migration = new ClassPathResource("db/migration/V4__structured_user_address.sql");
        assertTrue(migration.exists(), "structured address migration must exist");
        String sql;
        try (InputStream input = migration.getInputStream()) {
            sql = new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
        assertTrue(sql.contains("province"));
        assertTrue(sql.contains("detail_address"));
    }

    private StandardEnvironment applicationEnvironment() throws IOException {
        ClassPathResource applicationYaml = new ClassPathResource("application.yml");
        YamlPropertySourceLoader loader = new YamlPropertySourceLoader();
        StandardEnvironment environment = new StandardEnvironment();
        MutablePropertySources sources = environment.getPropertySources();
        sources.remove(StandardEnvironment.SYSTEM_PROPERTIES_PROPERTY_SOURCE_NAME);
        sources.remove(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME);
        for (PropertySource<?> source : loader.load("application", applicationYaml)) {
            sources.addLast(source);
        }
        sources.addLast(new PropertiesPropertySource("empty", new java.util.Properties()));
        return environment;
    }
}

