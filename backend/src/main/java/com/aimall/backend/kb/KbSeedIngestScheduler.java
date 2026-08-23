package com.aimall.backend.kb;

import com.aimall.backend.config.AppProperties;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbDocMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;

/** Dispatches generated seed ingestion with bounded concurrency and stale-task recovery. */
@Slf4j
@Component
@RequiredArgsConstructor
public class KbSeedIngestScheduler {

    private final KbDocMapper kbDocMapper;
    private final KbService kbService;
    private final AppProperties props;
    private final KbSeedCatalog catalog;

    @Scheduled(fixedDelayString = "${app.seed.knowledge-base.dispatch-delay-ms:10000}", initialDelayString = "${app.seed.knowledge-base.dispatch-initial-delay-ms:5000}")
    public void dispatchNextBatch() {
        var config = props.getSeed().getKnowledgeBase();
        if (!config.isEnabled()) {
            return;
        }
        try {
            List<KbDoc> all = kbDocMapper.selectList(new LambdaQueryWrapper<KbDoc>()
                    .in(KbDoc::getTitle, catalog.documents().stream().map(KbSeedDocument::title).toList())
                    .orderByAsc(KbDoc::getId));
            List<KbDoc> selected = plan(all, LocalDateTime.now(), config.getBatchSize(),
                    config.getMaxConcurrent(), config.getStuckTimeoutSeconds());
            for (KbDoc doc : selected) {
                kbService.dispatchSeedDocument(doc);
            }
            if (!selected.isEmpty()) {
                log.info("dispatched {} generated knowledge seed(s)", selected.size());
            }
        } catch (Exception e) {
            log.warn("bulk seed dispatch failed: {}", e.getMessage());
        }
    }

    static List<KbDoc> plan(List<KbDoc> docs, LocalDateTime now, int batchSize,
                            int maxConcurrent, int stuckTimeoutSeconds) {
        if (batchSize <= 0 || maxConcurrent <= 0) {
            return List.of();
        }
        LocalDateTime cutoff = now.minusSeconds(Math.max(1, stuckTimeoutSeconds));
        long freshProcessing = docs.stream()
                .filter(doc -> "PROCESSING".equals(doc.getStatus()))
                .filter(doc -> doc.getUpdatedAt() == null || !doc.getUpdatedAt().isBefore(cutoff))
                .count();
        int capacity = Math.max(0, maxConcurrent - (int) freshProcessing);
        int limit = Math.min(batchSize, capacity);
        if (limit == 0) {
            return List.of();
        }
        return docs.stream()
                .filter(doc -> isEligible(doc, cutoff))
                .sorted(Comparator.comparing(KbDoc::getId))
                .limit(limit)
                .toList();
    }

    private static boolean isEligible(KbDoc doc, LocalDateTime cutoff) {
        if ("PENDING".equals(doc.getStatus()) || "FAILED".equals(doc.getStatus())) {
            return true;
        }
        return "PROCESSING".equals(doc.getStatus())
                && doc.getUpdatedAt() != null && doc.getUpdatedAt().isBefore(cutoff);
    }
}
