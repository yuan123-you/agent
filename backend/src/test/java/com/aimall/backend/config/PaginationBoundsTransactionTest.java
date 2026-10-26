package com.aimall.backend.config;

import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.spring.MybatisSqlSessionFactoryBean;
import java.util.UUID;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.session.SqlSessionFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import static org.assertj.core.api.Assertions.assertThat;

class PaginationBoundsTransactionTest {
    public interface ProbeMapper {
        @Select("SELECT id FROM pagination_probe ORDER BY id")
        IPage<Long> rows(IPage<Long> page);
    }
    private SqlSessionFactory factory;
    @BeforeEach
    void setup() throws Exception {
        var source = new DriverManagerDataSource("jdbc:h2:mem:page_" + UUID.randomUUID() + ";MODE=MySQL;DB_CLOSE_DELAY=-1", "sa", "");
        var jdbc = new JdbcTemplate(source);
        jdbc.execute("CREATE TABLE pagination_probe (id BIGINT PRIMARY KEY)");
        jdbc.update("INSERT INTO pagination_probe SELECT X FROM SYSTEM_RANGE(1, 550)");
        var builder = new MybatisSqlSessionFactoryBean();
        var config = new MybatisConfiguration();
        config.addMapper(ProbeMapper.class);
        builder.setConfiguration(config); builder.setDataSource(source);
        builder.setPlugins(new MybatisPlusConfig().mybatisPlusInterceptor());
        factory = builder.getObject();
    }
    @Test
    void negativeSizeCannotDisableTheActualSqlPagination() {
        try (var session = factory.openSession()) {
            var result = session.getMapper(ProbeMapper.class).rows(new Page<>(1, -1));
            assertThat(result.getRecords()).hasSize(500);

            assertThat(result.getSize()).isEqualTo(500);
        }
    }
    @Test
    void oversizedPageIsBoundedBeforeSqlExecution() {
        try (var session = factory.openSession()) {
            var result = session.getMapper(ProbeMapper.class).rows(new Page<>(1, Long.MAX_VALUE));
            assertThat(result.getRecords()).hasSize(500);
        }
    }
    @Test
    void ordinaryPagingStillReturnsTheRequestedSlice() {
        try (var session = factory.openSession()) {
            var result = session.getMapper(ProbeMapper.class).rows(new Page<>(2, 20));
            assertThat(result.getRecords()).hasSize(20).startsWith(21L).endsWith(40L);
        }
    }
}
