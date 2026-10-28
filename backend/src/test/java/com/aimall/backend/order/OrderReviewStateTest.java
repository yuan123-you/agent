package com.aimall.backend.order;

import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.OrderItem;
import com.aimall.backend.mapper.ProductReviewMapper;
import com.aimall.backend.product.ReviewControllerTest.SqlFixture;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class OrderReviewStateTest {
    private SqlFixture db;
    private AnnotationConfigApplicationContext context;
    private OrderService orders;
    private OrderController controller;
    private OrderInfo order;

    @BeforeEach void setUp() {
        db = new SqlFixture();
        orders = mock(OrderService.class);
        context = new AnnotationConfigApplicationContext();
        context.registerBean(OrderService.class, () -> orders);
        context.registerBean(OrderSseNotifier.class, () -> mock(OrderSseNotifier.class));
        context.registerBean(ProductReviewMapper.class, () -> db.context.getBean(ProductReviewMapper.class));
        context.registerBean(com.aimall.backend.aftersale.AfterSaleService.class,()->mock(com.aimall.backend.aftersale.AfterSaleService.class));
        context.registerBean(com.aimall.backend.aftersale.AfterSaleEvidenceStorage.class,()->mock(com.aimall.backend.aftersale.AfterSaleEvidenceStorage.class));
        context.register(OrderController.class);
        context.refresh();
        controller = context.getBean(OrderController.class);
        order = new OrderInfo(); order.setId(30L); order.setUserId(7L); order.setStatus("DELIVERED");
        when(orders.requireOwned(7L, 30L)).thenReturn(order);
        var item = item(40L, 1L);
        when(orders.itemsOf(30L)).thenReturn(List.of(item));
        var page = new Page<OrderInfo>(1, 20); page.setRecords(List.of(order)); page.setTotal(1);
        when(orders.myOrders(7L, null, 1, 20)).thenReturn(page);
    }

    @AfterEach void tearDown() { context.close(); db.close(); }

    @ParameterizedTest @CsvSource({
            "DELIVERED,NONE,false,true", "PENDING_PAYMENT,NONE,false,false", "PAID,NONE,false,false",
            "SHIPPED,NONE,false,false", "CANCELLED,NONE,false,false", "DELIVERED,OWN,true,false",
            "SHIPPED,OWN,true,false", "DELIVERED,DELETED,false,true", "DELIVERED,OTHER_USER,false,true",
            "DELIVERED,HISTORICAL,true,false"})
    void detailAndListExposePurchaseIdAndUserProductReviewState(String status, String review,
                                                               boolean reviewed, boolean canReview) {
        order.setStatus(status);
        if (!"NONE".equals(review)) {
            db.jdbc.update("insert into product_review(product_id,user_id,order_item_id,rating,content,deleted) values(1,?,?,5,'Review',?)",
                    "OTHER_USER".equals(review) ? 8L : 7L, "HISTORICAL".equals(review) ? null : 44L,
                    "DELETED".equals(review) ? 1 : 0);
        }
        assertState(firstItem(controller.detail(7L, 30L).getData()), 40L, reviewed, canReview);
        assertState(firstItem(controller.my(7L, null, 1, 20).getData().getRecords().get(0)), 40L, reviewed, canReview);
    }

    @Test void reviewingProductOnAnotherOrderDisablesEveryOccurrenceButNotOtherProducts() {
        db.jdbc.update("insert into product_review(product_id,user_id,order_item_id,rating,content,deleted) values(1,7,40,5,'Review',0)");
        when(orders.itemsOf(30L)).thenReturn(List.of(item(44L, 1L), item(43L, 2L)));
        var items = items(controller.detail(7L, 30L).getData());
        assertState(items.get(0), 44L, true, false);
        assertState(items.get(1), 43L, false, true);
    }

    @Test void historicalDuplicateReviewsDoNotBreakOrderVo() {
        db.jdbc.update("insert into product_review(product_id,user_id,rating,content,deleted) values(1,7,5,'Old',0),(1,7,4,'Duplicate',0)");
        assertState(firstItem(controller.detail(7L, 30L).getData()), 40L, true, false);
    }

    @Test void detailAndListPreserveActualDeliveryCompany() {
        order.setDeliveryCompany("圆通速递");
        order.setLogisticsNo("YT12345678");
        var detail = controller.detail(7L, 30L).getData();
        var listOrder = controller.my(7L, null, 1, 20).getData().getRecords().get(0);
        assertEquals("圆通速递", detail.get("deliveryCompany"));
        assertEquals("圆通速递", listOrder.get("deliveryCompany"));
        assertEquals("YT12345678", detail.get("logisticsNo"));
    }
    @Test void emptyOrderStillReturnsEmptyItems() {
        when(orders.itemsOf(30L)).thenReturn(List.of());
        assertTrue(items(controller.detail(7L, 30L).getData()).isEmpty());
    }

    private static OrderItem item(long id, long product) {
        var item = new OrderItem(); item.setId(id); item.setOrderId(30L); item.setProductId(product); return item;
    }
    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> items(Map<String, Object> vo) { return (List<Map<String, Object>>) vo.get("items"); }
    private static Map<String, Object> firstItem(Map<String, Object> vo) { return items(vo).get(0); }
    private static void assertState(Map<String, Object> item, long id, boolean reviewed, boolean canReview) {
        assertEquals(id, item.get("orderItemId"));
        assertEquals(reviewed, item.get("reviewed"));
        assertEquals(canReview, item.get("canReview"));
    }
}
