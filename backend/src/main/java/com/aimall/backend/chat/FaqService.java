package com.aimall.backend.chat;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * FAQ 关键词自动回答：命中知识库 markdown（平台规则种子文档"高频常见问答"章节）时，
 * 直接返回固定答案，不调用 AI 服务（节省 LLM 调用、响应更快）。
 * 单一来源 = 知识库 markdown：改一处（编辑 markdown）即生效，避免与硬编码答案双源漂移。
 * 缓存驱动：按文件修改时间失效重建；存储副本未生成时回退 classpath 种子。
 * 匹配策略：问题文本与用户消息的 CJK 双字滑窗交集 ≥2 视为命中（与 RAG 切词同思路），
 * 按文档顺序取第一个命中（阈值取 2 保精度，未命中自然回落 AI+RAG 兜底）。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FaqService {

    /** 与 KbService 一致的种子文档路径（FAQ 单一来源） */
    private static final String SEED_POLICY_CLASSPATH = "kbseed/platform-policies.md";

    /** 命中 FAQ 条目：`N. **问题？** 答案`（FAQ 章节条目均为"粗体问题以？结尾"格式） */
    private static final Pattern FAQ_ITEM = Pattern.compile(
            "\\*\\*(.+?[？?])\\*\\*\\s*(.+)$", Pattern.MULTILINE);

    // 中文切词：CJK 双字滑窗 + ASCII 词（与 ai-service product_index.tokenize 同思路）
    private static final Pattern CJK_RE = Pattern.compile("[\\u4e00-\\u9fff]+");
    private static final Pattern ASCII_RE = Pattern.compile("[a-zA-Z0-9][a-zA-Z0-9._\\-]+");

    /** 缓存：问题 → 答案（LinkedHashMap 保持文档顺序） */
    private volatile Map<String, String> cache = Map.of();
    private volatile long cacheMtime = Long.MIN_VALUE;

    /** 关键词 → FAQ 答案（未命中返回 null） */
    public String match(String content) {
        if (content == null || content.isBlank()) {
            return null;
        }
        ensureFresh();
        List<String> userTokens = tokenize(content);
        if (userTokens.isEmpty()) {
            return null;
        }
        for (Map.Entry<String, String> e : cache.entrySet()) {
            if (sharedTokenCount(userTokens, tokenize(e.getKey())) >= 2) {
                return e.getValue();
            }
        }
        return null;
    }

    /** 按需刷新缓存：直接读 classpath 种子（存储已迁移 MinIO，本地文件副本不再存在） */
    private void ensureFresh() {
        try {
            String md = readClasspathSeed();
            if (cacheMtime == Long.MIN_VALUE) {
                cache = parseFaqs(md);
                // 无 mtime 可比较，置位避免每次请求都重建（内容由 classpath 种子唯一决定）
                cacheMtime = 0L;
                log.info("faq cache initialized: {} entries", cache.size());
            }
        } catch (Exception e) {
            log.warn("faq cache refresh failed, keep old: {}", e.getMessage());
        }
    }

    private String readClasspathSeed() {
        try (var in = new ClassPathResource(SEED_POLICY_CLASSPATH).getInputStream()) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            return "";
        }
    }

    private Map<String, String> parseFaqs(String md) {
        Map<String, String> out = new LinkedHashMap<>();
        Matcher m = FAQ_ITEM.matcher(md);
        while (m.find()) {
            String q = m.group(1).trim();
            String a = m.group(2).trim();
            if (!q.isEmpty() && !a.isEmpty() && !out.containsKey(q)) {
                out.put(q, a);
            }
        }
        return out;
    }

    /** 中文双字滑窗 + ASCII 词切词（与 RAG 检索一致，避免整句无法匹配） */
    private static List<String> tokenize(String text) {
        String src = text == null ? "" : text;
        List<String> tokens = new ArrayList<>();
        Matcher am = ASCII_RE.matcher(src.toLowerCase());
        while (am.find()) {
            tokens.add(am.group());
        }
        Matcher cm = CJK_RE.matcher(src);
        while (cm.find()) {
            String seg = cm.group();
            if (seg.length() >= 2) {
                for (int i = 0; i + 2 <= seg.length(); i++) {
                    tokens.add(seg.substring(i, i + 2));
                }
            }
        }
        return tokens;
    }

    private static int sharedTokenCount(List<String> a, List<String> b) {
        int n = 0;
        for (String t : a) {
            if (b.contains(t)) {
                n++;
            }
        }
        return n;
    }
}
