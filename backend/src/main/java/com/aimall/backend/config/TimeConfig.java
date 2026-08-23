package com.aimall.backend.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.time.ZoneId;
import java.util.TimeZone;

@Configuration
public class TimeConfig {
    public static final ZoneId BEIJING_ZONE = ZoneId.of("Asia/Shanghai");

    public TimeConfig() {
        TimeZone.setDefault(TimeZone.getTimeZone(BEIJING_ZONE));
    }

    @Bean
    public Clock clock() {
        return Clock.system(BEIJING_ZONE);
    }
}
