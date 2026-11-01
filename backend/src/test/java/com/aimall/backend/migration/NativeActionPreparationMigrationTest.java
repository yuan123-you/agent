package com.aimall.backend.migration;

import com.aimall.backend.config.AppProperties;
import org.junit.jupiter.api.Test;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.*;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.sql.DriverManager;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class NativeActionPreparationMigrationTest {
    @Test void v20BackfillsExistingQuotesAndEnforcesPreparationUniquenessWithoutBreakingLegacyNullKeys() throws Exception {
        var resource=new ClassPathResource("db/migration/V20__agent_action_preparation.sql");
        String sql=resource.getContentAsString(StandardCharsets.UTF_8);
        assertTrue(sql.contains("CHARACTER SET ascii COLLATE ascii_bin"), "tool-call keys must remain case-sensitive on MySQL");
        try(var connection=DriverManager.getConnection("jdbc:h2:mem:native_v20;MODE=MySQL","sa","")) {
            var db=new JdbcTemplate(new SingleConnectionDataSource(connection,true));
            db.execute("create table agent_action(action_id varchar(64) primary key,user_id bigint,conversation_id bigint,amount decimal(10,2))");
            db.update("insert into agent_action values('legacy',7,20,19.90)");
            // H2 lacks MySQL per-column charset/collation and multi-ADD ALTER syntax.
            // Preserve the column/index definitions while expressing the same operations in H2's grammar.
            String h2Sql=sql.replace("\r\n", "\n").replace(" CHARACTER SET ascii COLLATE ascii_bin", "")
                    .replace(",\n  ADD", ";\nALTER TABLE agent_action ADD")
                    .replace("ADD UNIQUE KEY uk_agent_action_preparation", "ADD CONSTRAINT uk_agent_action_preparation UNIQUE");
            ScriptUtils.executeSqlScript(connection,new ByteArrayResource(h2Sql.getBytes(StandardCharsets.UTF_8)));
            assertEquals(new BigDecimal("19.90"),db.queryForObject("select original_amount from agent_action where action_id='legacy'",BigDecimal.class));
            assertNull(db.queryForObject("select preparation_key from agent_action where action_id='legacy'",String.class));
            assertEquals(Boolean.FALSE,db.queryForObject("select native_workflow_managed from agent_action where action_id='legacy'",Boolean.class));
            db.update("insert into agent_action(action_id,user_id,conversation_id) values('legacy-2',7,20)");
            db.update("insert into agent_action(action_id,user_id,conversation_id,preparation_key) values('native',7,20,'call')");
            assertThrows(org.springframework.dao.DuplicateKeyException.class,()->db.update(
                    "insert into agent_action(action_id,user_id,conversation_id,preparation_key) values('duplicate',7,20,'call')"));
            db.update("insert into agent_action(action_id,user_id,conversation_id,preparation_key) values('case-sensitive',7,20,'CALL')");
            db.update("insert into agent_action(action_id,user_id,conversation_id,preparation_key) values('other-conversation',7,21,'call')");
            assertEquals(5,db.queryForObject("select count(*) from agent_action",Integer.class));
        }
    }

    @Test void featureDefaultsOffAndYamlUsesSharedActionWorkflowsEnabledEnvironmentName() throws Exception {
        assertFalse(new AppProperties().getAi().isActionWorkflowsEnabled());
        var resource=new ClassPathResource("application.yml");
        assertTrue(resource.getContentAsString(StandardCharsets.UTF_8).contains("action-workflows-enabled: ${ACTION_WORKFLOWS_ENABLED:false}"));
        for(boolean enabled : new boolean[]{false,true}) {
            var environment=new StandardEnvironment();
            environment.getPropertySources().remove(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME);
            environment.getPropertySources().remove(StandardEnvironment.SYSTEM_PROPERTIES_PROPERTY_SOURCE_NAME);
            if(enabled) environment.getPropertySources().addFirst(new MapPropertySource("test",Map.of("ACTION_WORKFLOWS_ENABLED","true")));
            for(var source:new YamlPropertySourceLoader().load("application",resource)) environment.getPropertySources().addLast(source);
            assertEquals(Boolean.toString(enabled),environment.getProperty("app.ai.action-workflows-enabled"));
        }
    }
}
