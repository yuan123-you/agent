package com.aimall.backend.internal;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.stream.LongStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class Bm25RetrieverTest {
    private final Bm25Retriever retriever = new Bm25Retriever(1.5, 0.75);

    @Test void tokenizesChineseBigramsAndAsciiWords() {
        assertEquals(List.of("退换", "换货", "iphone15"),
                retriever.tokenize("退换货 iPhone15"));
    }

    @Test void ranksRareRelevantTermsFirst() {
        var corpus = List.of(
                new Bm25Retriever.Document(1L, 10L, null, "POLICY", "七天无理由退货", "退换货条款"),
                new Bm25Retriever.Document(2L, 11L, null, "POLICY", "七天配送说明", "配送条款"),
                new Bm25Retriever.Document(3L, 12L, null, "POLICY", "保修说明", "保修条款"));
        var hits = retriever.search("无理由退货", corpus, 20);
        assertEquals(1L, hits.get(0).document().chunkId());
        assertTrue(hits.get(0).score() > 0);
    }

    @Test void capsOutputAtTwenty() {
        var corpus = LongStream.rangeClosed(1, 30)
                .mapToObj(i -> new Bm25Retriever.Document(i, i, null, "FAQ", "退货规则" + i, "规则"))
                .toList();
        assertEquals(20, retriever.search("退货", corpus, 200).size());
    }
}