package com.aimall.backend.kb;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import static org.junit.jupiter.api.Assertions.*;

class KbSeedCatalogTest {
    @Test
    void load_parsesAndValidatesRealManifest() {
        KbSeedCatalog catalog = KbSeedCatalog.load(new ClassPathResource("kbseed/test/manifest.json"));
        assertEquals(1, catalog.documents().size());
        KbSeedDocument doc = catalog.documents().get(0);
        assertEquals("test-001", doc.key());
        assertEquals("FAQ", doc.docType());
        assertTrue(new ClassPathResource(doc.resource()).exists());
    }

    @Test
    void load_acceptsCommittedFormalKnowledgeManifest() {
        KbSeedCatalog catalog = KbSeedCatalog.load(new ClassPathResource("kbseed/generated/manifest.json"));
        assertEquals(15, catalog.documents().size());
        assertTrue(catalog.documents().stream().allMatch(doc -> doc.title().startsWith("AI Mall ")));
        assertTrue(catalog.documents().stream().noneMatch(doc -> doc.title().contains("合成测试")));
    }

    @Test
    void load_rejectsMissingManifest() {
        assertThrows(IllegalStateException.class,
                () -> KbSeedCatalog.load(new ClassPathResource("kbseed/test/missing.json")));
    }
}
