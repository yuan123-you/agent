package com.aimall.backend.chat;

import org.springframework.stereotype.Service;

/**
 * 保留 ChatService 的 FAQ 调用接口，统一由当前有效知识库及引用校验链路回答。
 * 打包的 FAQ 文本不携带 ACTIVE 状态、当前版本或引用证据，不能作为独立答案，
 * 检索或 AI 服务不可用时也不能回退到该文本。
 */
@Service
public class FaqService {

    /** 不生成未经当前证据校验的快捷答案，让调用方继续执行 AI/RAG 链路。 */
    public String match(String content) {
        return null;
    }
}
