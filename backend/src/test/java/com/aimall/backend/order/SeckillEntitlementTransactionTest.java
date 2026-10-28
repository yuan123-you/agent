package com.aimall.backend.order;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.config.MybatisPlusConfig;
import com.aimall.backend.entity.*;
import com.aimall.backend.mapper.*;
import com.aimall.backend.promotion.PromotionService;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.config.GlobalConfig;
import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.spring.MybatisSqlSessionFactoryBean;
import java.lang.reflect.Modifier;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import javax.sql.DataSource;
import org.apache.ibatis.session.SqlSessionFactory;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mybatis.spring.mapper.MapperFactoryBean;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import org.springframework.transaction.*;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/** Real order/promotion SQL: buyer quota is independent of campaign inventory and request boundaries. */
class SeckillEntitlementTransactionTest {
    @Configuration @EnableTransactionManagement(proxyTargetClass=true) @Import(MybatisPlusConfig.class)
    static class Config {
        @Bean Clock clock(){return Clock.systemDefaultZone();}
        @Bean DataSource ds(){return new DriverManagerDataSource("jdbc:h2:mem:quota_"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=10000","sa","");}
        @Bean JdbcTemplate jdbc(DataSource d){return new JdbcTemplate(d);}
        @Bean PlatformTransactionManager tm(DataSource d){return new DataSourceTransactionManager(d);}
        @Bean SqlSessionFactory factory(DataSource d,MybatisPlusInterceptor interceptor,MetaObjectHandler handler)throws Exception {
            var f=new MybatisSqlSessionFactoryBean();f.setDataSource(d);var c=new MybatisConfiguration();c.setMapUnderscoreToCamelCase(true);f.setConfiguration(c);f.setPlugins(interceptor);f.setGlobalConfig(new GlobalConfig().setMetaObjectHandler(handler));return f.getObject();
        }
        <T> MapperFactoryBean<T> mapper(Class<T> type,SqlSessionFactory f){var b=new MapperFactoryBean<>(type);b.setSqlSessionFactory(f);return b;}
        @Bean MapperFactoryBean<OrderInfoMapper> orders(SqlSessionFactory f){return mapper(OrderInfoMapper.class,f);}
        @Bean MapperFactoryBean<OrderItemMapper> items(SqlSessionFactory f){return mapper(OrderItemMapper.class,f);}
        @Bean MapperFactoryBean<ProductMapper> products(SqlSessionFactory f){return mapper(ProductMapper.class,f);}
        @Bean MapperFactoryBean<MallSkuMapper> skus(SqlSessionFactory f){return mapper(MallSkuMapper.class,f);}
        @Bean MapperFactoryBean<MallSeckillMapper> seckills(SqlSessionFactory f){return mapper(MallSeckillMapper.class,f);}
        @Bean PromotionService promotions(MallSeckillMapper s,ProductMapper p){return new PromotionService(mock(MallCouponMapper.class),mock(UserCouponMapper.class),s,p);}
        @Bean OrderService service(OrderInfoMapper o,OrderItemMapper i,ProductMapper p,MallSkuMapper s,PromotionService promo){return new OrderService(o,i,p,s,promo,mock(OrderSseNotifier.class),mock(AddressService.class));}
    }
    AnnotationConfigApplicationContext context;JdbcTemplate jdbc;OrderService service;
    @BeforeEach void setup(){
        context=new AnnotationConfigApplicationContext(Config.class);jdbc=context.getBean(JdbcTemplate.class);service=context.getBean(OrderService.class);
        table("product",Product.class);table("mall_sku",MallSku.class);table("mall_seckill",MallSeckill.class);table("order_info",OrderInfo.class);table("order_item",OrderItem.class);
        jdbc.execute("create table sys_user(id bigint primary key,deleted int default 0)");jdbc.update("insert into sys_user(id) values(7),(8)");
        jdbc.update("insert into product(id,name,status,price,stock,version,deleted) values(1,'Product','ON_SALE',10,20,0,0)");
        jdbc.update("insert into mall_seckill(id,product_id,seckill_price,seckill_stock,seckill_limit,start_time,end_time,status,version,deleted) values(1,1,2,10,1,?,?,'ENABLE',0,0)",LocalDateTime.now().minusHours(1),LocalDateTime.now().plusHours(1));
    }
    void table(String name,Class<?> type){
        var columns=new ArrayList<String>();
        for(var f:type.getDeclaredFields()){
            if(Modifier.isStatic(f.getModifiers()))continue;
            String c=f.getName().replaceAll("([a-z0-9])([A-Z])","$1_$2").toLowerCase(Locale.ROOT);
            Class<?> t=f.getType();String sql=t==Long.class?"bigint":t==Integer.class?"int":t==BigDecimal.class?"decimal(18,2)":t==LocalDateTime.class?"timestamp":"varchar(4096)";
            columns.add(c+(c.equals("id")?" bigint generated by default as identity primary key":" "+sql)+(c.equals("deleted")?" default 0":""));
        }jdbc.execute("create table "+name+"("+String.join(",",columns)+")");
    }
    @AfterEach void close(){jdbc.execute("drop all objects");context.close();}
    OrderInfo buy(long user){var r=new OrderDtos.CreateOrderRequest();r.setProductId(1L);r.setQuantity(1);r.setReceiverName("Buyer");r.setReceiverPhone("13800000000");r.setReceiverAddress("Address");return service.create(user,r,"USER",null);}
    int count(){return jdbc.queryForObject("select count(*) from order_info",Integer.class);}
    @ParameterizedTest @ValueSource(strings={"ENABLE","DISABLE"})
    void realSkuRowsBlockAggregateFallbackInAgentAndDirectOrderPaths(String status) {
        jdbc.update("insert into mall_sku(id,product_id,status,price,stock,version,deleted) values(3,1,?,12,0,0,0)",status);
        assertEquals(2108,assertThrows(BizException.class,()->buy(7)).getCode());
        assertEquals(2108,assertThrows(BizException.class,()->service.quoteForAgent(7L,1L,1)).getCode());
        assertEquals(0,count());assertEquals(10,jdbc.queryForObject("select seckill_stock from mall_seckill",Integer.class));
    }
    @Test void pendingPurchaseReservesPerBuyerQuotaButNotAnotherBuyers(){
        buy(7);assertEquals(2207,assertThrows(BizException.class,()->buy(7)).getCode());buy(8);assertEquals(2,count());
    }
    @Test void unpaidCancellationReleasesEntitlementAndCampaignStock(){
        var first=buy(7);service.cancel(7L,first.getId());buy(7);assertEquals(2,count());assertEquals(9,jdbc.queryForObject("select seckill_stock from mall_seckill",Integer.class));
    }
    @ParameterizedTest @ValueSource(strings={"PAID","SHIPPED","DELIVERED","REFUNDED"})
    void paidAndRefundedPurchasesRetainQuota(String status){
        var first=buy(7);jdbc.update("update order_info set status=? where id=?",status,first.getId());
        assertEquals(2207,assertThrows(BizException.class,()->buy(7)).getCode());assertEquals(1,count());
    }
    @Test void duplicateCheckoutLinesShareOneEntitlementAndRollbackAllReservations(){
        assertEquals(2207,assertThrows(BizException.class,()->service.checkout(7L,List.of(new OrderService.CheckoutItem(1L,0L,1),new OrderService.CheckoutItem(1L,0L,1)),null,"Buyer","13800000000","Address",null)).getCode());
        assertEquals(0,count());assertEquals(10,jdbc.queryForObject("select seckill_stock from mall_seckill",Integer.class));
    }
    @Test void duplicateLinesAtExactCampaignStockAndBuyerLimitAreAllowed() {
        jdbc.update("update mall_seckill set seckill_limit=2,seckill_stock=2");
        service.checkout(7L,List.of(new OrderService.CheckoutItem(1L,0L,1),new OrderService.CheckoutItem(1L,0L,1)),null,"Buyer","13800000000","Address",null);
        assertEquals(1,count());assertEquals(0,jdbc.queryForObject("select seckill_stock from mall_seckill",Integer.class));
    }
    @Test void concurrentRequestsHaveOnlyOneEntitlementWinner()throws Exception{
        var pool=Executors.newFixedThreadPool(2);var start=new CyclicBarrier(2);
        Callable<Boolean> command=()->{start.await();try{buy(7);return true;}catch(BizException e){assertEquals(2207,e.getCode());return false;}};
        try{var a=pool.submit(command);var b=pool.submit(command);assertNotEquals(a.get(15,TimeUnit.SECONDS),b.get(15,TimeUnit.SECONDS));}
        finally{pool.shutdownNow();}assertEquals(1,count());
    }
    @Test void agentQuotesDoNotReserveEntitlementAndRespectExistingPurchases(){
        assertEquals(new BigDecimal("2.00"),service.quoteForAgent(7L,1L,1));assertEquals(new BigDecimal("2.00"),service.quoteForAgent(7L,1L,1));assertEquals(0,count());
        buy(7);assertEquals(2207,assertThrows(BizException.class,()->service.quoteForAgent(7L,1L,1)).getCode());
    }
}
