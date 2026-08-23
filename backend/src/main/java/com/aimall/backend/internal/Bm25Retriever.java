package com.aimall.backend.internal;

import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** In-process Okapi BM25 retrieval for knowledge-base chunks. */
@Component
public class Bm25Retriever {
    private final double k1;
    private final double b;

    public Bm25Retriever() {
        this(1.5, 0.75);
    }

    public Bm25Retriever(double k1, double b) {
        this.k1 = k1;
        this.b = b;
    }

    public record Document(Long chunkId, Long docId, Long productId,
                           String docType, String content, String source) {}
    public record Hit(Document document, double score) {}

    public List<String> tokenize(String text) {
        if (text == null || text.isBlank()) {
            return List.of();
        }
        List<String> tokens = new ArrayList<>();
        StringBuilder chinese = new StringBuilder();
        StringBuilder ascii = new StringBuilder();
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (isChinese(ch)) {
                addAscii(tokens, ascii);
                chinese.append(ch);
            } else if (ch <= 0x7f && Character.isLetterOrDigit(ch)) {
                addChineseBigrams(tokens, chinese);
                ascii.append(Character.toLowerCase(ch));
            } else {
                addChineseBigrams(tokens, chinese);
                addAscii(tokens, ascii);
            }
        }
        addChineseBigrams(tokens, chinese);
        addAscii(tokens, ascii);
        return tokens;
    }

    public List<Hit> search(String query, List<Document> corpus, int requestedTopK) {
        List<String> queryTokens = tokenize(query);
        if (queryTokens.isEmpty() || corpus == null || corpus.isEmpty()) {
            return List.of();
        }
        Set<String> queryTerms = new HashSet<>(queryTokens);
        List<Map<String, Integer>> termFrequencies = new ArrayList<>();
        Map<String, Integer> documentFrequencies = new HashMap<>();
        double totalLength = 0;
        for (Document document : corpus) {
            Map<String, Integer> frequencies = new HashMap<>();
            for (String token : tokenize(document.content())) {
                frequencies.merge(token, 1, Integer::sum);
            }
            termFrequencies.add(frequencies);
            totalLength += frequencies.values().stream().mapToInt(Integer::intValue).sum();
            for (String term : queryTerms) {
                if (frequencies.containsKey(term)) {
                    documentFrequencies.merge(term, 1, Integer::sum);
                }
            }
        }

        int documentCount = corpus.size();
        double averageLength = totalLength / documentCount;
        List<Hit> hits = new ArrayList<>();
        for (int i = 0; i < corpus.size(); i++) {
            Map<String, Integer> frequencies = termFrequencies.get(i);
            int documentLength = frequencies.values().stream().mapToInt(Integer::intValue).sum();
            double score = 0;
            for (String term : queryTerms) {
                int frequency = frequencies.getOrDefault(term, 0);
                if (frequency == 0) {
                    continue;
                }
                int documentFrequency = documentFrequencies.getOrDefault(term, 0);
                double idf = Math.log(1 + (documentCount - documentFrequency + 0.5)
                        / (documentFrequency + 0.5));
                double denominator = frequency + k1 * (1 - b + b * documentLength / averageLength);
                score += idf * frequency * (k1 + 1) / denominator;
            }
            if (score > 0) {
                hits.add(new Hit(corpus.get(i), score));
            }
        }
        int topK = Math.max(1, Math.min(requestedTopK, 20));
        return hits.stream()
                .sorted(Comparator.comparingDouble(Hit::score).reversed()
                        .thenComparing(hit -> hit.document().chunkId(), Comparator.nullsLast(Long::compareTo)))
                .limit(topK)
                .toList();
    }

    private boolean isChinese(char ch) {
        return ch >= '\u4e00' && ch <= '\u9fff';
    }

    private void addChineseBigrams(List<String> tokens, StringBuilder chinese) {
        for (int i = 0; i + 1 < chinese.length(); i++) {
            tokens.add(chinese.substring(i, i + 2));
        }
        chinese.setLength(0);
    }

    private void addAscii(List<String> tokens, StringBuilder ascii) {
        if (!ascii.isEmpty()) {
            tokens.add(ascii.toString().toLowerCase(Locale.ROOT));
            ascii.setLength(0);
        }
    }
}