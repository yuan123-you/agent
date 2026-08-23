package com.aimall.backend.config;

import io.minio.MinioClient;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** 对象存储客户端：全部来自环境变量，禁止硬编码密钥 */
@Configuration
@RequiredArgsConstructor
public class MinioConfig {

    private final AppProperties props;

    @Bean
    public MinioClient minioClient() {
        return MinioClient.builder()
                .endpoint(props.getStorage().getEndpoint())
                .credentials(props.getStorage().getAccessKey(), props.getStorage().getSecretKey())
                .build();
    }
}