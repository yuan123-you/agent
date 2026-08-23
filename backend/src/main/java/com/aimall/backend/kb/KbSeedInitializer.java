package com.aimall.backend.kb;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Registers built-in and generated knowledge seeds at startup. */
@Slf4j
@Configuration
@RequiredArgsConstructor
public class KbSeedInitializer {
    private final KbService kbService;
    private final KbBulkSeedService bulkSeedService;

    @Bean
    public ApplicationRunner kbSeedRunner() {
        return args -> {
            log.info("kb seed initializing...");
            kbService.seedPolicyIfNeeded();
            bulkSeedService.ensureSeeds();
        };
    }
}
