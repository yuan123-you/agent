package com.aimall.backend.chat;
import java.sql.DriverManager;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import static org.junit.jupiter.api.Assertions.*;
class AiTraceMigrationTest {
    @Test void schemaKeepsUnknownTokensNullableAndEnforcesUniqueTraceIds() throws Exception {
        try(var connection=DriverManager.getConnection("jdbc:h2:mem:ai_trace_migration;MODE=MySQL","sa","")) {
            ScriptUtils.executeSqlScript(connection,new ClassPathResource("db/migration/V19__ai_execution_traces.sql"));
            var db=new JdbcTemplate(new SingleConnectionDataSource(connection,true));
            db.update("insert into ai_trace(trace_id,conversation_id,user_id,status,input_preview,created_at) values('run',7,1,'RUNNING','hello',CURRENT_TIMESTAMP)");
            assertNull(db.queryForObject("select total_tokens from ai_trace where trace_id='run'",Long.class));
            assertThrows(org.springframework.dao.DuplicateKeyException.class,()->db.update("insert into ai_trace(trace_id,conversation_id,user_id,status,input_preview,created_at) values('run',7,1,'RUNNING','hello',CURRENT_TIMESTAMP)"));
        }
    }
}
