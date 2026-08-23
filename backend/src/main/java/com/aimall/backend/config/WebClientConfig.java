package com.aimall.backend.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.ReactorResourceFactory;
import org.springframework.web.reactive.function.client.WebClient;

/**
 * WebClient 配置（非阻塞调用 AI 服务，禁止 RestTemplate）
 */
@Configuration
public class WebClientConfig {

    @Bean
    public ReactorResourceFactory reactorResourceFactory() {
        return new ReactorResourceFactory();
    }

    @Bean
    public WebClient aiWebClient(AppProperties props) {
        return WebClient.builder()
                .baseUrl(props.getAi().getBaseUrl())
                .build();
    }
}
