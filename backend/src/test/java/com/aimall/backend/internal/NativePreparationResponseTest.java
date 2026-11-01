package com.aimall.backend.internal;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.GlobalExceptionHandler;
import com.aimall.backend.mapper.*;
import com.aimall.backend.order.OrderService;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class NativePreparationResponseTest {
    private final AgentOrderActionService actions = mock(AgentOrderActionService.class);
    private final ActionWorkflowCoordinator workflows = mock(ActionWorkflowCoordinator.class);
    private final ObjectMapper json = new ObjectMapper().findAndRegisterModules();
    private record Preparation(String path, String actionId, String body, Object result) {}

    private List<Preparation> preparations() {
        Instant expiry = Instant.parse("2026-11-01T12:00:00Z");
        var create = new AgentOrderActionService.PrepareResult("act-create","Product",2,BigDecimal.TEN,
                new BigDecimal("20.00"),"Buyer","13800000000","Address",expiry);
        var cancel = new AgentOrderActionService.BusinessPrepareResult("ORDER_CANCEL","act-cancel",30L,"O30",
                null,null,null,null,"Changed mind",null,BigDecimal.ZERO,expiry);
        var after = new AgentOrderActionService.BusinessPrepareResult("AFTER_SALE_APPLY","act-after",30L,"O30",
                40L,"Product","RETURN_REFUND","QUALITY","Broken",1,BigDecimal.TEN,expiry);
        when(actions.prepare(any())).thenReturn(create);
        when(actions.prepareCancel(any())).thenReturn(cancel);
        when(actions.prepareAfterSale(any())).thenReturn(after);
        return List.of(
                new Preparation("/order/prepare","act-create","{\"userId\":7,\"conversationId\":20,\"productId\":10,\"quantity\":2}",create),
                new Preparation("/order/cancel/prepare","act-cancel","{\"userId\":7,\"conversationId\":20,\"orderId\":30,\"reason\":\"Changed mind\"}",cancel),
                new Preparation("/after-sale/prepare","act-after","{\"userId\":7,\"conversationId\":20,\"orderId\":30,\"orderItemId\":40,\"quantity\":1,\"reason\":\"Broken\"}",after));
    }

    private MockMvc mvc() {
        var controller = new InternalToolController(mock(ProductMapper.class),mock(OrderInfoMapper.class),
                mock(OrderService.class),mock(ConversationMapper.class),actions);
        ReflectionTestUtils.setField(controller,"workflows",workflows);
        return MockMvcBuilders.standaloneSetup(controller).setControllerAdvice(new GlobalExceptionHandler())
                .setMessageConverters(new MappingJackson2HttpMessageConverter(json)).build();
    }

    @Test void disabledAllThreePrepareResponsesKeepExactLegacyJsonWithoutWorkflowOrWrapper() throws Exception {
        var mvc = mvc();
        for (var preparation : preparations()) {
            var output = mvc.perform(post("/internal/tools"+preparation.path()).contentType("application/json")
                    .content(preparation.body())).andExpect(status().isOk()).andReturn().getResponse();
            assertEquals(json.writeValueAsString(ApiResponse.ok(preparation.result())),output.getContentAsString());
            verify(workflows,never()).start(7L,preparation.actionId());
        }
    }

    @ParameterizedTest
    @ValueSource(strings={"WAITING_APPROVAL","COMPLETED"})
    void enabledAllThreeKeepPreparationFieldsAndAddOnlyTopLevelWorkflowMetadata(String status) throws Exception {
        when(workflows.enabled()).thenReturn(true);
        var mvc = mvc();
        for (var preparation : preparations()) {
            Map<String,Object> metadata = Map.of("actionId",preparation.actionId(),"workflowStatus",status,
                    "nativeInterrupt",true,"interrupted","WAITING_APPROVAL".equals(status),"recoverable",true);
            // A replay may already have a receipt. Preparation must not masquerade as that confirmation.
            when(workflows.start(7L,preparation.actionId())).thenReturn(Map.of("workflow",metadata,
                    "orderId",999L,"receiverName","Different receipt"));
            var body = (ObjectNode)json.readTree(preparation.body());body.put("preparationKey","call-"+preparation.actionId());
            var output = mvc.perform(post("/internal/tools"+preparation.path()).contentType("application/json")
                    .content(json.writeValueAsString(body))).andExpect(status().isOk()).andReturn().getResponse();
            var expected = (ObjectNode)json.readTree(json.writeValueAsString(ApiResponse.ok(preparation.result())));
            ((ObjectNode)expected.get("data")).set("workflow",json.valueToTree(metadata));
            assertEquals(expected,json.readTree(output.getContentAsString()));
            verify(workflows).start(7L,preparation.actionId());
        }
        verify(actions).prepare(argThat(request -> "call-act-create".equals(request.preparationKey())));
        verify(actions).prepareCancel(argThat(request -> "call-act-cancel".equals(request.preparationKey())));
        verify(actions).prepareAfterSale(argThat(request -> "call-act-after".equals(request.preparationKey())));
    }

    @Test void startFailuresRemainFailuresForAllThreeInsteadOfReturningUnmarkedPreparedCards() throws Exception {
        when(workflows.enabled()).thenReturn(true);
        var mvc = mvc();
        for (var preparation : preparations()) {
            when(workflows.start(7L,preparation.actionId())).thenThrow(new ActionWorkflowClient.GatewayException(preparation.actionId(),503,true));
            mvc.perform(post("/internal/tools"+preparation.path()).contentType("application/json").content(preparation.body()))
                    .andExpect(status().isServiceUnavailable()).andExpect(jsonPath("$.data.actionId").value(preparation.actionId()))
                    .andExpect(jsonPath("$.data.recoverable").value(true)).andExpect(jsonPath("$.data.workflow").doesNotExist());
        }
    }
}
