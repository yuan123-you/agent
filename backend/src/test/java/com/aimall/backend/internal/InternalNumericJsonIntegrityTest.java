package com.aimall.backend.internal;

import com.aimall.backend.common.GlobalExceptionHandler;
import com.aimall.backend.common.BizException;
import com.aimall.backend.config.AppProperties;
import com.aimall.backend.config.InternalAuthFilter;
import com.aimall.backend.entity.*;
import com.aimall.backend.mapper.*;
import com.aimall.backend.order.OrderService;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;
import java.util.stream.Stream;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;
import org.mockito.ArgumentCaptor;
import org.springframework.http.MediaType;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class InternalNumericJsonIntegrityTest {
    private static final String TOKEN = "synthetic-test-token-not-a-real-secret";
    record Spec(Class<?> type,String route,String json) { }
    static final List<Spec> SPECS = List.of(
        new Spec(InternalToolController.ProductSearchBody.class,"/product/search","{\"userId\":7,\"topK\":2}"),
        new Spec(InternalToolController.ProductDetailBody.class,"/product/detail","{\"userId\":7,\"productId\":10}"),
        new Spec(InternalToolController.OrderQueryBody.class,"/order/query","{\"userId\":7}"),
        new Spec(InternalToolController.OrderCreateBody.class,"/order/prepare","{\"userId\":7,\"conversationId\":20,\"productId\":10,\"quantity\":2}"),
        new Spec(InternalToolController.EscalateBody.class,"/escalate","{\"userId\":7,\"conversationId\":20}"),
        new Spec(InternalToolController.OrderCancelBody.class,"/order/cancel/prepare","{\"userId\":7,\"conversationId\":20,\"orderId\":30}"),
        new Spec(InternalToolController.AfterSalePrepareBody.class,"/after-sale/prepare","{\"userId\":7,\"conversationId\":20,\"orderId\":30,\"orderItemId\":40,\"quantity\":2}"),
        new Spec(InternalToolController.OrderConfirmBody.class,"/order/confirm","{\"userId\":7,\"actionId\":\"act-test\"}"));
    static Stream<Arguments> invalidFields() {
        return SPECS.stream().flatMap(spec -> Arrays.stream(spec.type().getDeclaredFields())
            .filter(field -> field.getType() == Long.class || field.getType() == Integer.class)
            .flatMap(field -> {
                String base = field.getName().equals("userId") ? "7" : field.getName().equals("conversationId") ? "20"
                    : field.getName().equals("productId") ? "10" : field.getName().equals("orderId") ? "30"
                    : field.getName().equals("orderItemId") ? "40" : "2";
                String maximum = field.getType() == Long.class ? "9223372036854775808" : "2147483648";
                String minimum = field.getType() == Long.class ? "-9223372036854775809" : "-2147483649";
                return Stream.of(base+".5",base+".0000000000000000000000001",maximum,minimum,maximum+".0",minimum+".0")
                    .map(token -> Arguments.of(spec.route(),spec.json().replaceFirst("\""+field.getName()+"\":\\d+","\""+field.getName()+"\":"+token)));
            }));
    }
    private final ProductMapper products = mock(ProductMapper.class);
    private final OrderInfoMapper orders = mock(OrderInfoMapper.class);
    private final OrderService service = mock(OrderService.class);
    private final ConversationMapper conversations = mock(ConversationMapper.class);
    private final AgentOrderActionService actions = mock(AgentOrderActionService.class);
    private MockMvc mvc;
    @BeforeEach void setup() {
        SecurityContextHolder.clearContext();
        for (Class<?> type : List.of(Product.class,OrderInfo.class))
            TableInfoHelper.initTableInfo(new MapperBuilderAssistant(new MybatisConfiguration(),"internal-numeric-http"),type);
        var props = new AppProperties(); props.getAi().setInternalToken(TOKEN);
        mvc = MockMvcBuilders.standaloneSetup(new InternalToolController(products,orders,service,conversations,actions))
                .setControllerAdvice(new GlobalExceptionHandler()).addFilters(new InternalAuthFilter(props)).build();
        var product = new Product(); product.setId(10L); product.setName("Product"); product.setStatus("ON_SALE"); product.setPrice(BigDecimal.ZERO); product.setStock(1000);
        when(products.selectById(any())).thenReturn(product); when(products.selectList(any())).thenReturn(List.of());
        when(orders.selectList(any())).thenReturn(List.of());
        var conversation = new Conversation(); conversation.setId(20L); conversation.setUserId(7L); conversation.setStatus("ACTIVE");
        when(conversations.selectById(any())).thenReturn(conversation); when(conversations.updateById(any(Conversation.class))).thenReturn(1);
        when(actions.prepare(any())).thenReturn(new AgentOrderActionService.PrepareResult("act-test","Product",2,BigDecimal.ZERO,BigDecimal.ZERO,"Receiver","Phone","Address",Instant.EPOCH));
        var business = new AgentOrderActionService.BusinessPrepareResult("TYPE","act-test",30L,"ORD-30",40L,"Product","REFUND","OTHER","Reason",2,BigDecimal.ZERO,Instant.EPOCH);
        when(actions.prepareCancel(any())).thenReturn(business); when(actions.prepareAfterSale(any())).thenReturn(business);
        var order = new OrderInfo(); order.setId(30L); order.setOrderNo("ORD-30"); order.setStatus("PENDING_PAYMENT"); order.setTotalAmount(BigDecimal.ZERO);
        when(actions.confirm(any(),any())).thenReturn(order); when(service.itemsOf(any())).thenReturn(List.of());
    }
    @AfterEach void clearAuth() { SecurityContextHolder.clearContext(); }
    private void noEffects() { verifyNoInteractions(products,orders,service,conversations,actions); }
    @ParameterizedTest @MethodSource("invalidFields")
    void everyIntegralInternalFieldRejectsRawPrecisionOrRangeErrorsBeforeEffects(String route,String json) throws Exception {
        var result = mvc.perform(post("/internal/tools"+route).header("X-Internal-Token",TOKEN)
                .contentType(MediaType.APPLICATION_JSON).content(json))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(2001))
                .andExpect(jsonPath("$.message").value("请求体格式错误或字段类型不合法")).andReturn();
        assertFalse(result.getResponse().getContentAsString().contains(TOKEN)); noEffects();
    }
    @ParameterizedTest @NullSource @ValueSource(strings = {"","incorrect-test-token"})
    void realInternalFilterRejectsMissingOrInvalidTokensBeforeBusiness(String token) throws Exception {
        var request = post("/internal/tools/order/prepare").contentType(MediaType.APPLICATION_JSON)
                .content("{\"userId\":7,\"conversationId\":20,\"productId\":10,\"quantity\":2}");
        if (token != null) request.header("X-Internal-Token",token);
        var result = mvc.perform(request).andExpect(status().isUnauthorized()).andExpect(jsonPath("$.code").value(1003)).andReturn();
        assertFalse(result.getResponse().getContentAsString().contains(TOKEN)); noEffects();
    }
    @ParameterizedTest @ValueSource(strings = {"2","2.0","2e0","\"2\"","150.0"})
    void exactPrepareTokensKeepInternalDefaultsAndNoNewGlobal99Cap(String token) throws Exception {
        mvc.perform(post("/internal/tools/order/prepare").header("X-Internal-Token",TOKEN).contentType(MediaType.APPLICATION_JSON)
                .content("{\"userId\":7.0,\"conversationId\":20e0,\"productId\":\"10\",\"quantity\":"+token+"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0)).andExpect(jsonPath("$.data.amount").value(0));
        var captured = ArgumentCaptor.forClass(AgentOrderActionService.PrepareRequest.class);
        verify(actions).prepare(captured.capture()); assertEquals(token.startsWith("150") ? 150 : 2,captured.getValue().quantity());
        assertEquals(7L,captured.getValue().userId()); assertEquals(20L,captured.getValue().conversationId()); assertEquals(10L,captured.getValue().productId());
        assertTrue(SecurityContextHolder.getContext().getAuthentication().getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_INTERNAL")));
        verifyNoInteractions(products,orders,service,conversations);
    }
    @ParameterizedTest @ValueSource(strings = {"",",\"quantity\":null"})
    void missingOrNullQuantitiesStillDefaultToOneInExistingPrepareEndpoints(String quantity) throws Exception {
        mvc.perform(post("/internal/tools/order/prepare").header("X-Internal-Token",TOKEN).contentType(MediaType.APPLICATION_JSON)
                .content("{\"userId\":7,\"conversationId\":20,\"productId\":10"+quantity+"}")).andExpect(status().isOk());
        mvc.perform(post("/internal/tools/after-sale/prepare").header("X-Internal-Token",TOKEN).contentType(MediaType.APPLICATION_JSON)
                .content("{\"userId\":7,\"conversationId\":20,\"orderId\":30,\"orderItemId\":40"+quantity+"}")).andExpect(status().isOk());
        var prepare = ArgumentCaptor.forClass(AgentOrderActionService.PrepareRequest.class); verify(actions).prepare(prepare.capture()); assertEquals(1,prepare.getValue().quantity());
        var sale = ArgumentCaptor.forClass(AgentOrderActionService.AfterSalePrepareRequest.class); verify(actions).prepareAfterSale(sale.capture()); assertEquals(1,sale.getValue().quantity());
    }
    @Test void existingConversationOwnershipIsStillEnforced() throws Exception {
        mvc.perform(post("/internal/tools/escalate").header("X-Internal-Token",TOKEN).contentType(MediaType.APPLICATION_JSON)
                .content("{\"userId\":8.0,\"conversationId\":20.0}"))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.code").value(2003));
        verify(conversations).selectById(20L); verify(conversations,never()).updateById(any(Conversation.class)); verifyNoInteractions(actions,service);
    }
    @Test void servicePermissionFailureIsNotBypassedByExactBinding() throws Exception {
        when(actions.prepare(any())).thenThrow(new BizException(2003,"无权操作该会话"));
        mvc.perform(post("/internal/tools/order/prepare").header("X-Internal-Token",TOKEN).contentType(MediaType.APPLICATION_JSON)
                .content("{\"userId\":7,\"conversationId\":20,\"productId\":10,\"quantity\":2.0}"))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.code").value(2003));
        verifyNoInteractions(products,orders,service,conversations);
    }
    @Test void decimalPriceFiltersAndExistingTopKClampAreUntouched() throws Exception {
        mvc.perform(post("/internal/tools/product/search").header("X-Internal-Token",TOKEN).contentType(MediaType.APPLICATION_JSON)
                .content("{\"userId\":7,\"topK\":150.0,\"minPrice\":0.01,\"maxPrice\":12.50}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.total").value(0));
        verify(products).selectList(argThat(wrapper -> wrapper.getSqlSegment().endsWith("LIMIT 10")));
    }
    @Test void confirmKeepsExactUserIdAndExistingResponseContract() throws Exception {
        mvc.perform(post("/internal/tools/order/confirm").header("X-Internal-Token",TOKEN).contentType(MediaType.APPLICATION_JSON)
                .content("{\"userId\":9007199254740993.0,\"actionId\":\"act-test\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.orderId").value(30)).andExpect(jsonPath("$.data.orderNo").value("ORD-30"))
                .andExpect(jsonPath("$.data.totalAmount").value(0)).andExpect(jsonPath("$.data.link").value("mall://order/30"));
        verify(actions).confirm(9007199254740993L,"act-test"); verify(service).itemsOf(30L);
    }
}
