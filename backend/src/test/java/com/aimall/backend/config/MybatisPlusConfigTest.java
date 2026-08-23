package com.aimall.backend.config;

import com.aimall.backend.entity.User;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.apache.ibatis.reflection.MetaObject;
import org.apache.ibatis.reflection.SystemMetaObject;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class MybatisPlusConfigTest {
    @BeforeAll
    static void initUserTableInfo() {
        TableInfoHelper.initTableInfo(new MapperBuilderAssistant(new MybatisConfiguration(), ""), User.class);
    }

    @Test
    void autoFillUsesInjectedClockInAsiaShanghai() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-23T04:05:06Z"), ZoneId.of("Asia/Shanghai"));
        MetaObjectHandler handler = new MybatisPlusConfig().metaObjectHandler(clock);
        User user = new User();
        MetaObject metaObject = SystemMetaObject.forObject(user);

        handler.insertFill(metaObject);

        LocalDateTime expected = LocalDateTime.of(2026, 8, 23, 12, 5, 6);
        assertThat(user.getCreatedAt()).isEqualTo(expected);
        assertThat(user.getUpdatedAt()).isEqualTo(expected);
    }
}
