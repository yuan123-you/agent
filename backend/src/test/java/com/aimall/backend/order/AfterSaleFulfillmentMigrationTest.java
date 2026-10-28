package com.aimall.backend.order;

import com.aimall.backend.entity.AfterSale;
import java.sql.DriverManager;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import static org.junit.jupiter.api.Assertions.*;

class AfterSaleFulfillmentMigrationTest {
    @Test void fulfillmentMarkerIsPersistedWithZeroDefault() throws Exception {
        assertEquals(Integer.class,AfterSale.class.getDeclaredField("cancelledFulfillmentQuantity").getType());
        assertEquals(0,AfterSale.class.getMethod("getCancelledFulfillmentQuantity").invoke(new AfterSale()));
    }
    @Test void migrationBackfillsOnlyUnambiguouslyUnshippedRefunds() throws Exception {
        var resource = new ClassPathResource("db/migration/V16__after_sale_fulfillment_quantity.sql");
        assertTrue(resource.exists(),"V16 must persist the per-case fulfillment reduction");
        try (var connection=DriverManager.getConnection("jdbc:h2:mem:fulfillment_migration;MODE=MySQL","sa","")) {
            var db=new JdbcTemplate(new SingleConnectionDataSource(connection,true));
            db.execute("create table order_info(id bigint primary key,status varchar(30),shipped_at timestamp)");
            db.execute("create table after_sale(id bigint primary key,order_id bigint,service_type varchar(30),status varchar(30),quantity int)");
            db.update("insert into order_info values(1,'PAID',null),(2,'SHIPPED',CURRENT_TIMESTAMP),(3,'REFUNDED',null)");
            db.update("insert into after_sale values(1,1,'REFUND_ONLY','REFUNDED',1),(2,2,'REFUND_ONLY','REFUNDED',2),(3,1,'RETURN_REFUND','REFUNDED',3),(4,1,'REFUND_ONLY','WAITING_REFUND',4),(5,3,'REFUND_ONLY','REFUNDED',5)");
            ScriptUtils.executeSqlScript(connection,resource);
            assertEquals(java.util.List.of(1,0,0,0,0),db.queryForList("select cancelled_fulfillment_quantity from after_sale order by id",Integer.class));
            assertEquals(0,db.queryForObject("select column_default from information_schema.columns where table_name='AFTER_SALE' and column_name='CANCELLED_FULFILLMENT_QUANTITY'",Integer.class));
        }
    }
}
