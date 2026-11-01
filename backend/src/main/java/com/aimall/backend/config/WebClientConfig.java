package com.aimall.backend.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.ReactorResourceFactory;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import reactor.netty.http.client.HttpClient;
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
                // Reactor Netty otherwise retries a connection-reset request once, even without Reactor retry().
                .clientConnector(new ReactorClientHttpConnector(HttpClient.create().disableRetry(true)))
                .build();
    }
}
