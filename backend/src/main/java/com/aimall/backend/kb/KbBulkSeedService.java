package com.aimall.backend.kb;

import com.aimall.backend.config.AppProperties;
import com.aimall.backend.config.ObjectStorage;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbDocMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Idempotently registers generated seed documents without flooding the ingest API. */
@Slf4j
@Service
@RequiredArgsConstructor
public class KbBulkSeedService {
    private final KbDocMapper kbDocMapper;
    private final ObjectStorage storage;
    private final AppProperties props;
    private final KbSeedCatalog catalog;

    public record SeedResult(int created, int existing, int failed) {
    }

    @Transactional
    public SeedResult ensureSeeds() {
        if (!props.getSeed().getKnowledgeBase().isEnabled()) {
            return new SeedResult(0, 0, 0);
        }
        int created = 0;
        int existing = 0;
        int failed = 0;
        for (KbSeedDocument seed : catalog.documents()) {
            KbDoc found = kbDocMapper.selectOne(new LambdaQueryWrapper<KbDoc>()
                    .eq(KbDoc::getTitle, seed.title()).last("LIMIT 1"));
            if (found != null) {
                existing++;
                continue;
            }
            String storedName = "seed-" + seed.key() + "." + seed.fileFormat().toLowerCase();
            try (var input = new ClassPathResource(seed.resource()).getInputStream()) {
                storage.put(storedName, input, contentType(seed.fileFormat()));
                KbDoc doc = new KbDoc();
                doc.setProductId(null);
                doc.setTitle(seed.title());
                doc.setDocType(seed.docType());
                doc.setFileUrl(storedName);
                doc.setFileFormat(seed.fileFormat());
                doc.setStatus("PENDING");
                doc.setVersion(1);
                doc.setCreatedBy(1L);
                kbDocMapper.insert(doc);
                created++;
            } catch (Exception e) {
                failed++;
                log.warn("seed document registration failed key={}: {}", seed.key(), e.getMessage());
            }
        }
        log.info("bulk knowledge seeds ensured: created={} existing={} failed={}", created, existing, failed);
        return new SeedResult(created, existing, failed);
    }

    private String contentType(String format) {
        return switch (format) {
            case "MD" -> "text/markdown";
            case "TXT" -> "text/plain";
            case "PDF" -> "application/pdf";
            default -> "application/octet-stream";
        };
    }
}
