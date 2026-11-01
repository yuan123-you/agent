package com.aimall.backend.config;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import reactor.netty.http.client.HttpClient;

import static org.junit.jupiter.api.Assertions.*;

class WebClientSingleAttemptTest {
    @Test void configuredConnectorDisablesNettyConnectionResetRetry() {
        var props = new AppProperties(); props.getAi().setBaseUrl("http://not-used.invalid");
        var web = new WebClientConfig().aiWebClient(props);
        Object exchange = ReflectionTestUtils.getField(web,"exchangeFunction");
        Object connector = ReflectionTestUtils.getField(exchange,"connector");
        var client = (HttpClient) ReflectionTestUtils.getField(connector,"httpClient");
        assertNotNull(client); assertTrue(client.configuration().isRetryDisabled());
    }
}
