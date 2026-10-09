package com.aimall.backend.config;

import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * 数据初始化：将种子用户占位密码重置为 BCrypt(seed-password)
 */
@Slf4j
@Configuration
@RequiredArgsConstructor
public class SeedDataInitializer {

    @Bean
    public ApplicationRunner seedPasswordResetter(UserMapper userMapper,
                                                  PasswordEncoder passwordEncoder,
                                                  AppProperties props) {
        return args -> {
            var pending = userMapper.selectList(
                    new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<User>()
                            .eq(User::getPassword, "SEED_RESET"));
            String password = props.getSeed().getPassword();
            if (!pending.isEmpty() && (password == null || password.isBlank())) {
                throw new IllegalStateException("SEED_PASSWORD must be supplied before initializing seed accounts");
            }
            int count = 0;
            for (User u : pending) {
                User update = new User();
                update.setId(u.getId());
                update.setPassword(passwordEncoder.encode(password));
                userMapper.updateById(update);
                count++;
            }
            if (count > 0) {
                log.info("seed password reset for {} users", count);
            }
        };
    }
}
