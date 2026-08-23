package com.aimall.backend.kb;

import com.aimall.backend.config.AppProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;

@Configuration
public class KbSeedCatalogConfiguration {
    @Bean
    public KbSeedCatalog kbSeedCatalog(AppProperties props) {
        return KbSeedCatalog.load(new ClassPathResource(props.getSeed().getKnowledgeBase().getManifest()));
    }
}
