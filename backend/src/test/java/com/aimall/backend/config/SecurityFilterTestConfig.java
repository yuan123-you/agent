package com.aimall.backend.config;

import com.aimall.backend.mapper.UserMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;

import static org.mockito.Mockito.mock;

/** Real MVC/security wiring with only persistence and Redis replaced; no application startup jobs. */
@Configuration
@EnableWebMvc
@Import({SecurityConfig.class, JwtAuthFilter.class, InternalAuthFilter.class})
public class SecurityFilterTestConfig {
    @Bean
    AppProperties appProperties() {
        AppProperties props = new AppProperties();
        props.getJwt().setSecret("synthetic-p1-regression-key-not-for-deployment-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ");
        props.getAi().setInternalToken("synthetic-internal-token");
        return props;
    }

    @Bean
    JwtService jwtService(AppProperties props) {
        return new JwtService(props);
    }

    @Bean
    UserMapper userMapper() {
        return mock(UserMapper.class);
    }

    @Bean
    StringRedisTemplate redisTemplate() {
        return mock(StringRedisTemplate.class);
    }
}
