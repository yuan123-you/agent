package com.aimall.backend.kb;

import com.aimall.backend.config.AppProperties;
import com.aimall.backend.config.ObjectStorage;
import com.aimall.backend.entity.KbChunk;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbChunkMapper;
import com.aimall.backend.mapper.KbDocMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/** Idempotently registers generated seed documents without flooding the ingest API. */
@Slf4j
@Service
@RequiredArgsConstructor
public class KbBulkSeedService {
    private final KbDocMapper kbDocMapper;
    private final KbChunkMapper kbChunkMapper;
    private final ObjectStorage storage;
    private final AppProperties props;
    private final KbSeedCatalog catalog;

    public record SeedResult(int created, int existing, int failed, int pruned) {
    }

    @Transactional
    public SeedResult ensureSeeds() {
        if (!props.getSeed().getKnowledgeBase().isEnabled()) {
            return new SeedResult(0, 0, 0, 0);
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
        int pruned = pruneStaleGeneratedSeeds();
        log.info("bulk knowledge seeds ensured: created={} existing={} failed={} pruned={}",
                created, existing, failed, pruned);
        return new SeedResult(created, existing, failed, pruned);
    }

    private int pruneStaleGeneratedSeeds() {
        Set<String> expectedFiles = catalog.documents().stream()
                .map(seed -> "seed-" + seed.key() + "." + seed.fileFormat().toLowerCase())
                .collect(Collectors.toSet());
        List<Long> staleIds = kbDocMapper.selectList(new LambdaQueryWrapper<KbDoc>()
                        .likeRight(KbDoc::getFileUrl, "seed-synthetic-kb-"))
                .stream()
                .filter(doc -> !expectedFiles.contains(doc.getFileUrl()))
                .map(KbDoc::getId)
                .toList();
        if (staleIds.isEmpty()) {
            return 0;
        }
        kbChunkMapper.delete(new LambdaQueryWrapper<KbChunk>().in(KbChunk::getDocId, staleIds));
        kbDocMapper.delete(new LambdaQueryWrapper<KbDoc>().in(KbDoc::getId, staleIds));
        return staleIds.size();
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
