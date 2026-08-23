package com.aimall.backend.kb;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Loads and validates the generated seed manifest before any database writes occur. */
public final class KbSeedCatalog {
    private static final Set<String> TYPES = Set.of("FAQ", "INTRO", "POLICY");
    private static final Set<String> FORMATS = Set.of("MD", "TXT", "PDF");
    private final List<KbSeedDocument> documents;

    private KbSeedCatalog(List<KbSeedDocument> documents) {
        this.documents = List.copyOf(documents);
    }

    public List<KbSeedDocument> documents() {
        return documents;
    }

    public static KbSeedCatalog load(Resource manifestResource) {
        try (var input = manifestResource.getInputStream()) {
            Manifest manifest = new ObjectMapper().readValue(input, Manifest.class);
            if (manifest.version() != 1 || manifest.documents() == null || manifest.documents().isEmpty()) {
                throw new IllegalArgumentException("unsupported or empty knowledge-base seed manifest");
            }
            validate(manifest.documents());
            return new KbSeedCatalog(manifest.documents());
        } catch (Exception e) {
            throw new IllegalStateException("无法加载知识库种子清单 " + manifestResource + ": " + e.getMessage(), e);
        }
    }

    private static void validate(List<KbSeedDocument> documents) {
        Set<String> keys = new HashSet<>();
        Set<String> titles = new HashSet<>();
        for (KbSeedDocument doc : documents) {
            if (doc.key() == null || doc.key().isBlank() || !keys.add(doc.key())) {
                throw new IllegalArgumentException("invalid or duplicate seed key: " + doc.key());
            }
            if (doc.title() == null || doc.title().isBlank() || !titles.add(doc.title())) {
                throw new IllegalArgumentException("invalid or duplicate seed title: " + doc.title());
            }
            if (!TYPES.contains(doc.docType()) || !FORMATS.contains(doc.fileFormat())) {
                throw new IllegalArgumentException("unsupported seed type/format: " + doc.key());
            }
            if (doc.resource() == null || !doc.resource().startsWith("kbseed/")
                    || !new ClassPathResource(doc.resource()).exists()) {
                throw new IllegalArgumentException("missing seed resource: " + doc.resource());
            }
            if (doc.charCount() <= 0 || doc.estimatedChunkCount() <= 0) {
                throw new IllegalArgumentException("invalid seed statistics: " + doc.key());
            }
        }
    }

    private record Manifest(int version, String generatedAt, long seed, List<KbSeedDocument> documents) {
    }
}

