package com.aimall.backend.aftersale;

import com.aimall.backend.entity.*;
import com.aimall.backend.mapper.*;
import com.aimall.backend.promotion.PromotionService;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.extension.spring.MybatisSqlSessionFactoryBean;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.ibatis.session.SqlSessionFactory;
import org.mybatis.spring.mapper.MapperFactoryBean;
import org.junit.jupiter.api.*;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import javax.sql.DataSource;
import java.lang.reflect.Modifier;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;

class AfterSaleTransactionTest {
    @Configuration @EnableTransactionManagement static class Config {
        @Bean DataSource dataSource(){return new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=10000","sa","");}
        @Bean PlatformTransactionManager transactions(DataSource ds){return new DataSourceTransactionManager(ds);}
        @Bean SqlSessionFactory factory(DataSource ds)throws Exception{var f=new MybatisSqlSessionFactoryBean();f.setDataSource(ds);var config=new MybatisConfiguration();config.setMapUnderscoreToCamelCase(true);f.setConfiguration(config);return f.getObject();}
        <T> MapperFactoryBean<T> mapper(Class<T> cls,SqlSessionFactory f){var bean=new MapperFactoryBean<>(cls);bean.setSqlSessionFactory(f);return bean;}
        @Bean MapperFactoryBean<OrderInfoMapper> orders(SqlSessionFactory f){return mapper(OrderInfoMapper.class,f);}
        @Bean MapperFactoryBean<OrderItemMapper> items(SqlSessionFactory f){return mapper(OrderItemMapper.class,f);}
        @Bean MapperFactoryBean<ProductMapper> products(SqlSessionFactory f){return mapper(ProductMapper.class,f);}
        @Bean MapperFactoryBean<MallSkuMapper> skus(SqlSessionFactory f){return mapper(MallSkuMapper.class,f);}
        @Bean MapperFactoryBean<AfterSaleMapper> cases(SqlSessionFactory f){return mapper(AfterSaleMapper.class,f);}
        @Bean MapperFactoryBean<MerchantMapper> merchants(SqlSessionFactory f){return mapper(MerchantMapper.class,f);}
        @Bean com.aimall.backend.order.OrderService orderService(OrderInfoMapper o,OrderItemMapper i,ProductMapper p,MallSkuMapper s){return new com.aimall.backend.order.OrderService(o,i,p,s,mock(PromotionService.class),mock(com.aimall.backend.order.OrderSseNotifier.class),mock(com.aimall.backend.address.AddressService.class));}
        @Bean AfterSaleEvidenceStorage storage(){return new AfterSaleEvidenceStorage(System.getProperty("java.io.tmpdir")+"/aimall-test-evidence");}
        @Bean AfterSaleService workflow(OrderInfoMapper o,OrderItemMapper i,ProductMapper p,MallSkuMapper s,AfterSaleMapper a,MerchantMapper m){return new AfterSaleService(o,i,p,s,a,m,mock(PromotionService.class),new ObjectMapper(),Clock.systemUTC());}
    }
    AnnotationConfigApplicationContext context;JdbcTemplate jdbc;AfterSaleService service;
    @BeforeEach void setup(){context=new AnnotationConfigApplicationContext(Config.class);jdbc=new JdbcTemplate(context.getBean(DataSource.class));service=context.getBean(AfterSaleService.class);
        table("order_info",OrderInfo.class);table("order_item",OrderItem.class);table("product",Product.class);table("mall_sku",MallSku.class);table("after_sale",AfterSale.class);table("merchant",Merchant.class);
        jdbc.execute("create unique index action_key on after_sale(action_id)");
        jdbc.update("insert into order_info(id,user_id,status,total_amount,order_no) values(1,7,'PAID',80,'ORDER1')");
        jdbc.update("insert into product(id,name,price,status,stock,version,deleted) values(3,'测试商品',50,'ON_SALE',5,1,0)");
        jdbc.update("insert into order_item(id,order_id,product_id,quantity,price,subtotal,product_name) values(2,1,3,2,50,100,'测试商品')");
    }
    void table(String name,Class<?> type){var columns=new ArrayList<String>();for(var field:type.getDeclaredFields()){if(Modifier.isStatic(field.getModifiers()))continue;String n=field.getName().replaceAll("([a-z0-9])([A-Z])","$1_$2").toLowerCase(Locale.ROOT);String sql=field.getType()==BigDecimal.class?"decimal(16,2)":field.getType()==LocalDateTime.class?"timestamp":Number.class.isAssignableFrom(field.getType())?"bigint":field.getType()==Boolean.class?"boolean":"varchar(16000)";columns.add(n+(n.equals("id")?" bigint auto_increment primary key":" "+sql));}jdbc.execute("create table "+name+"("+String.join(",",columns)+")");}
    @AfterEach void close(){context.close();}
    AfterSale apply(String type,String amount){return service.apply(7L,new AfterSaleService.Apply(1L,2L,type,"PERSONAL","商品不合适",1,new BigDecimal(amount),List.of(),UUID.randomUUID().toString()),null,null);}
    AfterSaleService.Command command(String action){return new AfterSaleService.Command(action,null,"验收人","010-00000000","测试退货地址","测试物流","TEST123",false);}
    @Test void concurrentApplicationsReserveTheItemOnlyOnce()throws Exception{
        var pool=Executors.newFixedThreadPool(2);var start=new CountDownLatch(1);try{
            Callable<Boolean> task=()->{start.await();try{apply("REFUND_ONLY","40");return true;}catch(com.aimall.backend.common.BizException e){return false;}};
            var a=pool.submit(task);var b=pool.submit(task);start.countDown();assertNotEquals(a.get(10,TimeUnit.SECONDS),b.get(10,TimeUnit.SECONDS));
            assertEquals(1,jdbc.queryForObject("select count(*) from after_sale",Integer.class));
        }finally{pool.shutdownNow();}
    }
    @Test void concurrentRefundReplaysNeverRestockOrRefundTwice()throws Exception{
        AfterSale c=apply("REFUND_ONLY","40");service.act(9L,"ADMIN",c.getId(),command("APPROVE"));
        var pool=Executors.newFixedThreadPool(2);try{var a=pool.submit(()->service.act(9L,"ADMIN",c.getId(),command("REFUND")));var b=pool.submit(()->service.act(9L,"ADMIN",c.getId(),command("REFUND")));assertEquals(a.get(10,TimeUnit.SECONDS).getRefundReference(),b.get(10,TimeUnit.SECONDS).getRefundReference());assertEquals(6,jdbc.queryForObject("select stock from product where id=3",Integer.class));}finally{pool.shutdownNow();}
        AfterSale second=apply("REFUND_ONLY","40");service.act(9L,"ADMIN",second.getId(),command("APPROVE"));service.act(9L,"ADMIN",second.getId(),command("REFUND"));
        assertEquals("REFUNDED",jdbc.queryForObject("select status from order_info where id=1",String.class));assertEquals(new BigDecimal("80.00"),service.refundedAmount(1L));
    }
    @Test void failedSkuReservationRollsBackProductStockAndShipmentState(){
        jdbc.update("update order_info set status='DELIVERED' where id=1");jdbc.update("insert into mall_sku(id,product_id,status,stock,version,deleted) values(99,3,'DISABLE',2,1,0)");jdbc.update("update order_item set sku_id=99 where id=2");
        AfterSale c=apply("EXCHANGE","0");service.act(9L,"ADMIN",c.getId(),command("APPROVE"));service.act(7L,"CUSTOMER",c.getId(),command("RETURN"));service.act(9L,"ADMIN",c.getId(),command("RECEIVE"));
        assertThrows(com.aimall.backend.common.BizException.class,()->service.act(9L,"ADMIN",c.getId(),command("SHIP_EXCHANGE")));
        assertEquals(5,jdbc.queryForObject("select stock from product where id=3",Integer.class));assertEquals("WAITING_EXCHANGE",jdbc.queryForObject("select status from after_sale where id=?",String.class,c.getId()));
    }

    @Test void openRefundBlocksDispatchUntilBuyerWithdraws() {
        AfterSale c=apply("REFUND_ONLY","40");var fulfillment=context.getBean(com.aimall.backend.order.OrderService.class);
        assertThrows(com.aimall.backend.common.BizException.class,()->fulfillment.ship(1L,"TRACK1","测试物流"));
        service.act(7L,"CUSTOMER",c.getId(),command("CANCEL"));fulfillment.ship(1L,"TRACK1","测试物流");
        assertEquals("SHIPPED",jdbc.queryForObject("select status from order_info where id=1",String.class));
    }
    @Test void sellableReturnRestocksOnlyAtReceiptAndNeverAgainAtRefund() {
        jdbc.update("update order_info set status='DELIVERED' where id=1");AfterSale c=apply("RETURN_REFUND","40");
        service.act(9L,"ADMIN",c.getId(),command("APPROVE"));service.act(7L,"CUSTOMER",c.getId(),command("RETURN"));
        service.act(9L,"ADMIN",c.getId(),new AfterSaleService.Command("RECEIVE",null,null,null,null,null,null,true));
        assertEquals(6,jdbc.queryForObject("select stock from product where id=3",Integer.class));service.act(9L,"ADMIN",c.getId(),command("REFUND"));
        assertEquals(6,jdbc.queryForObject("select stock from product where id=3",Integer.class));assertEquals("DELIVERED",jdbc.queryForObject("select status from order_info where id=1",String.class));
    }
    @Test void replacementDispatchAndBuyerReceiptDoNotPretendToRefundMoney() {
        jdbc.update("update order_info set status='DELIVERED' where id=1");AfterSale c=apply("EXCHANGE","0");
        service.act(9L,"ADMIN",c.getId(),command("APPROVE"));service.act(7L,"CUSTOMER",c.getId(),command("RETURN"));service.act(9L,"ADMIN",c.getId(),command("RECEIVE"));service.act(9L,"ADMIN",c.getId(),command("SHIP_EXCHANGE"));
        AfterSale finished=service.act(7L,"CUSTOMER",c.getId(),command("CONFIRM_EXCHANGE"));assertEquals("EXCHANGED",finished.getStatus());assertNull(finished.getRefundReference());assertEquals(4,jdbc.queryForObject("select stock from product where id=3",Integer.class));assertEquals(BigDecimal.ZERO,service.refundedAmount(1L));
    }

    @Test void acceptedExchangeCanBecomeARefundWithoutShippingOrRestockingTwice() {
        jdbc.update("update order_info set status='DELIVERED' where id=1");AfterSale c=apply("EXCHANGE","0");
        service.act(9L,"ADMIN",c.getId(),command("APPROVE"));service.act(7L,"CUSTOMER",c.getId(),command("RETURN"));service.act(9L,"ADMIN",c.getId(),command("RECEIVE"));
        AfterSale converted=service.act(7L,"CUSTOMER",c.getId(),command("CONVERT_REFUND"));assertEquals("WAITING_REFUND",converted.getStatus());assertEquals(new BigDecimal("40.00"),converted.getApprovedRefundAmount());
        service.act(9L,"ADMIN",c.getId(),command("REFUND"));assertEquals(new BigDecimal("40.00"),service.refundedAmount(1L));assertEquals(5,jdbc.queryForObject("select stock from product where id=3",Integer.class));
    }
}
