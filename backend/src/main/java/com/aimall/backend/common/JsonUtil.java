package com.aimall.backend.common;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.util.Map;

/**
 * JSON 工具（SSE 事件解析/增强用）
 */
public final class JsonUtil {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private JsonUtil() {
    }

    public static JsonNode parse(String json) {
        try {
            return MAPPER.readTree(json);
        } catch (Exception e) {
            return null;
        }
    }

    public static String write(Object obj) {
        try {
            return MAPPER.writeValueAsString(obj);
        } catch (Exception e) {
            return String.valueOf(obj);
        }
    }

    /** JSON 字符串 → Map（解析失败返回空 Map） */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> toMap(String json) {
        try {
            return MAPPER.readValue(json, Map.class);
        } catch (Exception e) {
            return new java.util.HashMap<>();
        }
    }

    /** 在 JSON 字符串上补充字段（如 done 事件补 messageId） */
    public static String putField(String json, String key, Object value) {
        try {
            JsonNode node = MAPPER.readTree(json);
            ObjectNode objectNode = node.isObject() ? (ObjectNode) node : MAPPER.createObjectNode();
            objectNode.putPOJO(key, value);
            return MAPPER.writeValueAsString(objectNode);
        } catch (Exception e) {
            return json;
        }
    }
}
