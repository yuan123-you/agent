package com.aimall.backend.chat;

import com.aimall.backend.common.*;
import com.aimall.backend.entity.AiTrace;
import com.aimall.backend.mapper.AiTraceMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import java.time.*;
import java.util.*;
import java.util.regex.Pattern;

/** Best-effort diagnostic writes, strict administrator reads. No dependency on Langfuse. */
@Service
@RequiredArgsConstructor
@Slf4j
public class AiTraceService {
    private final AiTraceMapper mapper;
    private static final Set<String> STATUSES = Set.of("RUNNING", "SUCCESS", "DEGRADED", "FAILED", "CANCELLED");
    private static final Pattern PRIVATE = Pattern.compile("password|passwd|authorization|api[_-]?key|secret|access[_-]?token|refresh[_-]?token|internal[_-]?token|reasoning|thinking|chain_of_thought|additional_kwargs|phone|email|address", Pattern.CASE_INSENSITIVE);
    private static LocalDateTime now() { return LocalDateTime.now(ZoneId.of("Asia/Shanghai")); }

    public String begin(Long userId, Long conversationId, String input) {
        String id=UUID.randomUUID().toString();
        try {
            var row=new AiTrace(); row.setTraceId(id); row.setUserId(userId); row.setConversationId(conversationId);
            row.setInputPreview(text(input,500)); row.setStatus("RUNNING"); row.setCreatedAt(now());
            row.setModelCalls(0); row.setStageCount(0); mapper.insert(row);
        } catch (RuntimeException e) { log.warn("AI trace initial write unavailable: {}",e.getClass().getSimpleName()); }
        return id;
    }

    public void record(String traceId, String raw) {
        if (traceId == null || raw == null || raw.length()>300_000) return;
        try {
            JsonNode node=JsonUtil.parse(raw);
            if (node==null || !traceId.equals(node.path("traceId").asText()) || !node.path("stages").isArray()) return;
            AiTrace row=find(traceId); if (row==null) return;
            JsonNode cleaned=sanitize(node,0);
            ArrayNode stages=(ArrayNode) cleaned.path("stages");
            long tokens=0; boolean usageKnown=false; int modelCalls=0;
            for (JsonNode stage: stages) {
                if (!"model".equals(stage.path("kind").asText())) continue;
                modelCalls++;
                JsonNode usage=stage.has("usage") ? stage.path("usage") : stage.path("output").path("usage");
                if (usage.path("total_tokens").isNumber()) {
                    tokens+=Math.max(0,usage.path("total_tokens").asLong()); usageKnown=true;
                }
            }
            // Background snapshots must never overwrite a concurrently completed status/owner.
            var update=new AiTrace(); update.setId(row.getId());
            update.setModelCalls(modelCalls); update.setTotalTokens(usageKnown?tokens:null);
            update.setStageCount(stages.size()); update.setDetailJson(cleaned.toString()); mapper.updateById(update);
        } catch (RuntimeException e) { log.warn("AI trace snapshot unavailable: {}",e.getClass().getSimpleName()); }
    }

    public void finish(String traceId, Long messageId, String status) {
        if (traceId==null) return;
        try {
            AiTrace row=find(traceId); if (row==null) return;
            var update=new AiTrace(); update.setId(row.getId());
            update.setStatus(STATUSES.contains(status)?status:"FAILED"); update.setMessageId(messageId);
            update.setFinishedAt(now()); update.setDurationMs(Math.max(0,Duration.between(row.getCreatedAt(),update.getFinishedAt()).toMillis()));
            mapper.updateById(update);
        } catch (RuntimeException e) { log.warn("AI trace completion unavailable: {}",e.getClass().getSimpleName()); }
    }

    public PageResult<Map<String,Object>> list(String status, Long conversationId, String query, long page, long size) {
        var filter=new LambdaQueryWrapper<AiTrace>().select(AiTrace::getId,AiTrace::getTraceId,AiTrace::getUserId,
                AiTrace::getConversationId,AiTrace::getMessageId,AiTrace::getStatus,AiTrace::getInputPreview,
                AiTrace::getModelCalls,AiTrace::getTotalTokens,AiTrace::getStageCount,AiTrace::getDurationMs,
                AiTrace::getCreatedAt,AiTrace::getFinishedAt);
        if (status!=null && !status.isBlank()) {
            if (!STATUSES.contains(status)) throw new BizException(1001,"无效的链路状态");
            filter.eq(AiTrace::getStatus,status);
        }
        if (conversationId!=null) filter.eq(AiTrace::getConversationId,conversationId);
        if (query!=null && !query.isBlank()) filter.like(AiTrace::getInputPreview,query.strip().substring(0,Math.min(80,query.strip().length())));
        filter.orderByDesc(AiTrace::getCreatedAt).orderByDesc(AiTrace::getId);
        return PageResult.of(mapper.selectPage(new Page<>(Math.max(1,page),Math.min(100,Math.max(1,size))),filter),this::summary);
    }

    public Map<String,Object> detail(String traceId) {
        AiTrace row=find(traceId); if (row==null) throw new BizException(1004,"链路不存在");
        Map<String,Object> result=summary(row); JsonNode data=JsonUtil.parse(row.getDetailJson());
        result.put("stages",data!=null?data.path("stages"):List.of());
        result.put("omittedStages",data!=null?data.path("omittedStages").asInt():0);
        result.put("error",data!=null?data.path("error").asText(null):null);
        return result;
    }

    public Map<String, Object> getLatestBenchmark() {
        try (var in = getClass().getClassLoader().getResourceAsStream("eval/benchmark_report.json")) {
            if (in != null) {
                String content = new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
                JsonNode node = JsonUtil.parse(content);
                if (node != null && node.isObject()) {
                    return JsonUtil.toMap(content);
                }
            }
        } catch (Exception e) {
            log.warn("failed to read bundled benchmark report from classpath: {}", e.getMessage());
        }
        for (java.nio.file.Path path : List.of(
                java.nio.file.Path.of("/srv/aimall/repo/eval/results/benchmark_report.json"),
                java.nio.file.Path.of("..", "eval", "results", "benchmark_report.json"),
                java.nio.file.Path.of("eval", "results", "benchmark_report.json"),
                java.nio.file.Path.of("D:", "studyAgent", "AI Mall", "eval", "results", "benchmark_report.json"))) {
            if (java.nio.file.Files.exists(path)) {
                try {
                    String content = java.nio.file.Files.readString(path, java.nio.charset.StandardCharsets.UTF_8);
                    JsonNode node = JsonUtil.parse(content);
                    if (node != null && node.isObject()) {
                        return JsonUtil.toMap(content);
                    }
                } catch (Exception e) {
                    log.warn("failed to read benchmark report from {}: {}", path, e.getMessage());
                }
            }
        }
        return Map.of("available", false, "message", "暂无评测报告");
    }

    private AiTrace find(String id) { return mapper.selectOne(new LambdaQueryWrapper<AiTrace>().eq(AiTrace::getTraceId,id)); }
    private Map<String,Object> summary(AiTrace row) {
        var result=new LinkedHashMap<String,Object>();
        result.put("traceId",row.getTraceId()); result.put("conversationId",row.getConversationId()); result.put("userId",row.getUserId());
        result.put("messageId",row.getMessageId()); result.put("status",row.getStatus()); result.put("inputPreview",row.getInputPreview());
        result.put("modelCalls",row.getModelCalls()); result.put("totalTokens",row.getTotalTokens()); result.put("stageCount",row.getStageCount());
        result.put("durationMs",row.getDurationMs()); result.put("createdAt",row.getCreatedAt()); result.put("finishedAt",row.getFinishedAt()); return result;
    }

    private static JsonNode sanitize(JsonNode node,int depth) {
        if (depth>9) return TextNode.valueOf("[depth limit]");
        if (node.isObject()) {
            if (Set.of("reasoning","thinking").contains(node.path("type").asText())) return TextNode.valueOf("[REDACTED]");
            ObjectNode out=JsonNodeFactory.instance.objectNode(); int count=0;
            var fields=node.fields();
            while (fields.hasNext() && count++<32) {
                var entry=fields.next(); out.set(entry.getKey(), PRIVATE.matcher(entry.getKey()).find()?TextNode.valueOf("[REDACTED]"):sanitize(entry.getValue(),depth+1));
            }
            return out;
        }
        if (node.isArray()) {
            ArrayNode out=JsonNodeFactory.instance.arrayNode(); int count=0;
            for (JsonNode child:node) { if (count++>=96) break; out.add(sanitize(child,depth+1)); } return out;
        }
        return node.isTextual()?TextNode.valueOf(text(node.asText(),6000)):node;
    }
    private static String text(String value,int limit) {
        if (value==null) return "";
        String s=value.substring(0,Math.min(value.length(),Math.max(limit,4000)));
        s=s.replaceAll("(?is)<think>.*?(?:</think>|$)","[REDACTED]");
        s=s.replaceAll("(?i)Bearer\\s+[^\\s,;，；]+","Bearer [REDACTED]")
                .replaceAll("[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}","[EMAIL]")
                .replaceAll("(?<!\\d)1[3-9]\\d{9}(?!\\d)","[PHONE]")
                .replaceAll("\\b(?:sk-|tvly-)[A-Za-z0-9_-]{8,}","[SECRET]")
                .replaceAll("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+","[JWT]");
        s=s.replaceAll("(?i)(?:api[_-]?key|password|internal[_-]?token)[\"']?\\s*[:=]\\s*[\"']?[^\\s,;\"']+","[SECRET]");
        return s.length()>limit?s.substring(0,limit-1)+"…":s;
    }
}
