package com.aimall.backend.order;

import java.sql.DriverManager;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import static org.junit.jupiter.api.Assertions.*;

class OrderShippingMetadataMigrationTest {
    @Test void productionColumnsAcceptApprovedTrackingAndCarrierBounds() throws Exception {
        var resource=new ClassPathResource("db/migration/V17__shipping_metadata_lengths.sql");
        assertTrue(resource.exists(),"Shipping bounds require an additive migration from existing VARCHAR(64) columns");
        try(var connection=DriverManager.getConnection("jdbc:h2:mem:shipping_metadata;MODE=MySQL","sa","")){
            var db=new JdbcTemplate(new SingleConnectionDataSource(connection,true));
            db.execute("create table order_info(id bigint primary key,logistics_no varchar(64),delivery_company varchar(64))");
            ScriptUtils.executeSqlScript(connection,resource);
            db.update("insert into order_info values(1,?,?)","T".repeat(100),"C".repeat(80));
            assertEquals(100,db.queryForObject("select length(logistics_no) from order_info",Integer.class));
            assertEquals(80,db.queryForObject("select length(delivery_company) from order_info",Integer.class));
            assertThrows(org.springframework.dao.DataIntegrityViolationException.class,()->db.update("insert into order_info values(2,?,null)","T".repeat(101)));
            assertThrows(org.springframework.dao.DataIntegrityViolationException.class,()->db.update("insert into order_info values(3,'TRACK',?)","C".repeat(81)));
        }
    }
}
