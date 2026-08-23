package com.aimall.backend.chat;

import com.aimall.backend.common.JsonUtil;
import com.aimall.backend.config.AppProperties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * AI 服务客户端：WebClient 非阻塞消费 SSE 流（禁止 RestTemplate）
 * <p>轻量熔断：连续失败 5 次打开 30 秒，期间快速失败，30 秒后半开放行探测。</p>
 */
@Slf4j
@Service
public class AiClient {

    private static final int FAILURE_THRESHOLD = 5;
    private static final long OPEN_MILLIS = 30_000L;

    private final WebClient webClient;
    private final AppProperties props;

    private final AtomicInteger consecutiveFailures = new AtomicInteger(0);
    private volatile long openUntil = 0L;

    public AiClient(WebClient aiWebClient, AppProperties props) {
        this.webClient = aiWebClient;
        this.props = props;
    }

    /** 对话流：订阅 AI 服务 SSE，逐事件透传给前端（熔断 OPEN 时快速失败） */
    public Flux<org.springframework.http.codec.ServerSentEvent<String>> streamChat(Map<String, Object> body) {
        if (isCircuitOpen()) {
            return Flux.error(new IllegalStateException("AI 服务熔断中，请稍后重试"));
        }
        return webClient.post().uri("/v1/chat/stream")
                .header("X-Internal-Token", props.getAi().getInternalToken())
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(body)
                .retrieve()
                .bodyToFlux(new ParameterizedTypeReference<org.springframework.http.codec.ServerSentEvent<String>>() {
                })
                .timeout(Duration.ofSeconds(180))
                .doOnComplete(this::recordSuccess)
                .doOnError(this::recordFailure);
    }

    /** 触发文档摄取（异步任务，AI 服务 202 返回） */
    public Mono<Void> triggerIngest(Map<String, Object> body) {
        return webClient.post().uri("/v1/kb/ingest")
                .header("X-Internal-Token", props.getAi().getInternalToken())
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .toBodilessEntity()
                .then();
    }

    /** 删除文档向量（version>0 时保留该版本） */
    public Mono<Void> deleteVectors(Long docId, int version) {
        return webClient.delete()
                .uri(b -> b.path("/v1/kb/docs/{id}").queryParam("version", version).build(docId))
                .header("X-Internal-Token", props.getAi().getInternalToken())
                .retrieve()
                .toBodilessEntity()
                .onErrorResume(e -> {
                    log.warn("delete vectors failed doc={}: {}", docId, e.getMessage());
                    return Mono.empty();
                })
                .then();
    }

    /** 会话摘要压缩（返回 summary 文本；失败返回空） */
    public Mono<String> summarize(Map<String, Object> body) {
        return webClient.post().uri("/v1/chat/summarize")
                .header("X-Internal-Token", props.getAi().getInternalToken())
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .map(s -> {
                    var node = JsonUtil.parse(s);
                    return node != null ? node.path("summary").asText("") : "";
                })
                .onErrorResume(e -> {
                    log.warn("summarize failed: {}", e.getMessage());
                    return Mono.just("");
                });
    }

    // ---------- 轻量熔断 ----------

    private boolean isCircuitOpen() {
        return System.currentTimeMillis() < openUntil;
    }

    private void recordSuccess() {
        consecutiveFailures.set(0);
    }

    private void recordFailure(Throwable e) {
        int failures = consecutiveFailures.incrementAndGet();
        if (failures >= FAILURE_THRESHOLD) {
            openUntil = System.currentTimeMillis() + OPEN_MILLIS;
            consecutiveFailures.set(0);
            log.warn("circuit OPEN for {}ms after {} consecutive failures", OPEN_MILLIS, failures);
        }
    }
}

