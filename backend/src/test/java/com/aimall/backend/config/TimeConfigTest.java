package com.aimall.backend.config;

import org.junit.jupiter.api.Test;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.PropertySource;
import org.springframework.core.io.ClassPathResource;

import java.io.IOException;
import java.time.ZoneId;
import java.util.TimeZone;

import static org.junit.jupiter.api.Assertions.assertEquals;

class TimeConfigTest {
    private static final ZoneId BEIJING = ZoneId.of("Asia/Shanghai");

    @Test
    void configuresApplicationClockAndJvmDefaultForBeijingTime() {
        TimeZone original = TimeZone.getDefault();
        try {
            TimeZone.setDefault(TimeZone.getTimeZone("UTC"));

            TimeConfig config = new TimeConfig();

            assertEquals(BEIJING, config.clock().getZone());
            assertEquals(BEIJING, TimeZone.getDefault().toZoneId());
        } finally {
            TimeZone.setDefault(original);
        }
    }

    @Test
    void configuresDatabaseSessionsForBeijingTime() throws IOException {
        PropertySource<?> properties = new YamlPropertySourceLoader()
                .load("application", new ClassPathResource("application.yml"))
                .get(0);

        assertEquals("SET time_zone = '+08:00'",
                properties.getProperty("spring.datasource.hikari.connection-init-sql"));
    }
}
