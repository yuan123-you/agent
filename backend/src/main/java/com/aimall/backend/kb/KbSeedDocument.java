package com.aimall.backend.kb;

import java.util.List;

/** One deterministic document entry from the synthetic seed manifest. */
public record KbSeedDocument(
        String key,
        String title,
        String docType,
        String fileFormat,
        String resource,
        String topic,
        List<String> evalTags,
        int charCount,
        int estimatedChunkCount
) {
}
