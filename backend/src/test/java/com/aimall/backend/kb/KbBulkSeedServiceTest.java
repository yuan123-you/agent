package com.aimall.backend.kb;

import com.aimall.backend.config.AppProperties;
import com.aimall.backend.config.ObjectStorage;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbChunkMapper;
import com.aimall.backend.mapper.KbDocMapper;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.core.io.ClassPathResource;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

class KbBulkSeedServiceTest {
    private final KbDocMapper mapper = mock(KbDocMapper.class);
    private final KbChunkMapper chunkMapper = mock(KbChunkMapper.class);
    private final ObjectStorage storage = mock(ObjectStorage.class);
    private final AppProperties props = new AppProperties();
    private final KbSeedCatalog catalog = KbSeedCatalog.load(new ClassPathResource("kbseed/test/manifest.json"));
    private final KbBulkSeedService service = new KbBulkSeedService(mapper, chunkMapper, storage, props, catalog);

    @Test
    void ensureSeeds_registersAndStoresMissingDocumentWithoutTriggeringIngest() throws Exception {
        when(mapper.selectOne(any())).thenReturn(null);
        KbBulkSeedService.SeedResult result = service.ensureSeeds();
        assertEquals(1, result.created());
        assertEquals(0, result.existing());
        ArgumentCaptor<KbDoc> captor = ArgumentCaptor.forClass(KbDoc.class);
        verify(mapper).insert(captor.capture());
        KbDoc inserted = captor.getValue();
        assertEquals("测试 FAQ", inserted.getTitle());
        assertEquals("PENDING", inserted.getStatus());
        verify(storage).put(eq("seed-test-001.md"), any(), eq("text/markdown"));
    }

    @Test
    void ensureSeeds_isIdempotentByTitle() throws Exception {
        KbDoc existing = new KbDoc();
        existing.setId(7L);
        when(mapper.selectOne(any())).thenReturn(existing);
        KbBulkSeedService.SeedResult result = service.ensureSeeds();
        assertEquals(0, result.created());
        assertEquals(1, result.existing());
        verify(mapper, never()).insert(any(KbDoc.class));
        verify(storage, never()).put(any(), any(), any());
    }

    @Test
    void ensureSeeds_prunesGeneratedDocumentsMissingFromManifest() {
        KbDoc existing = new KbDoc();
        existing.setId(7L);
        when(mapper.selectOne(any())).thenReturn(existing);

        KbDoc stale = new KbDoc();
        stale.setId(88L);
        stale.setFileUrl("seed-synthetic-kb-999.md");
        when(mapper.selectList(any())).thenReturn(List.of(stale));

        KbBulkSeedService.SeedResult result = service.ensureSeeds();

        assertEquals(1, result.pruned());
        verify(chunkMapper).delete(any());
        verify(mapper).delete(any());
    }

    @Test
    void ensureSeeds_doesNothingWhenDisabled() {
        props.getSeed().getKnowledgeBase().setEnabled(false);
        KbBulkSeedService.SeedResult result = service.ensureSeeds();
        assertEquals(0, result.created());
        verifyNoInteractions(mapper, chunkMapper, storage);
    }
}

