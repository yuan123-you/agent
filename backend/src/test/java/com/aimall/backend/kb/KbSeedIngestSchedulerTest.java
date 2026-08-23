package com.aimall.backend.kb;

import com.aimall.backend.entity.KbDoc;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

class KbSeedIngestSchedulerTest {
    private static KbDoc doc(long id, String status, LocalDateTime updatedAt) {
        KbDoc doc = new KbDoc();
        doc.setId(id);
        doc.setTitle("AI Mall 合成测试知识库 " + id);
        doc.setStatus(status);
        doc.setUpdatedAt(updatedAt);
        return doc;
    }

    @Test
    void plan_neverExceedsBatchOrAvailableConcurrency() {
        LocalDateTime now = LocalDateTime.of(2026, 8, 23, 12, 0);
        List<KbDoc> docs = List.of(
                doc(1, "PROCESSING", now.minusMinutes(1)),
                doc(2, "PROCESSING", now.minusMinutes(2)),
                doc(3, "PENDING", now), doc(4, "PENDING", now), doc(5, "PENDING", now));
        List<KbDoc> selected = KbSeedIngestScheduler.plan(docs, now, 3, 4, 900);
        assertEquals(List.of(3L, 4L), selected.stream().map(KbDoc::getId).toList());
    }

    @Test
    void plan_retriesFailedAndStaleButExcludesActiveAndFreshProcessing() {
        LocalDateTime now = LocalDateTime.of(2026, 8, 23, 12, 0);
        List<KbDoc> docs = List.of(
                doc(1, "ACTIVE", now.minusDays(1)),
                doc(2, "PROCESSING", now.minusMinutes(1)),
                doc(3, "PROCESSING", now.minusMinutes(20)),
                doc(4, "FAILED", now.minusMinutes(1)),
                doc(5, "DISABLED", now.minusDays(1)));
        List<KbDoc> selected = KbSeedIngestScheduler.plan(docs, now, 5, 4, 900);
        assertEquals(List.of(3L, 4L), selected.stream().map(KbDoc::getId).toList());
    }

    @Test
    void plan_returnsEmptyWhenConcurrencyIsFull() {
        LocalDateTime now = LocalDateTime.of(2026, 8, 23, 12, 0);
        List<KbDoc> docs = List.of(doc(1, "PROCESSING", now), doc(2, "PENDING", now));
        assertEquals(List.of(), KbSeedIngestScheduler.plan(docs, now, 2, 1, 900));
    }
}
