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
            User cond = new User();
            cond.setPassword("SEED_RESET");
            int count = 0;
            for (User u : userMapper.selectList(
                    new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<User>()
                            .eq(User::getPassword, "SEED_RESET"))) {
                User update = new User();
                update.setId(u.getId());
                update.setPassword(passwordEncoder.encode(props.getSeed().getPassword()));
                userMapper.updateById(update);
                count++;
            }
            if (count > 0) {
                log.info("seed password reset for {} users (default password: {})", count, props.getSeed().getPassword());
            }
        };
    }
}
