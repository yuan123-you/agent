package com.aimall.backend.kb;

import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class KbAdminControllerContentTest {
    @Test
    void contentReturnsPdfForInlineViewing() {
        KbService service = mock(KbService.class);
        byte[] bytes = "%PDF".getBytes(StandardCharsets.UTF_8);
        when(service.content(12L)).thenReturn(new KbService.DocumentContent("使用说明", "PDF", bytes));

        ResponseEntity<byte[]> response = new KbAdminController(service).content(12L);

        assertEquals(MediaType.APPLICATION_PDF, response.getHeaders().getContentType());
        assertTrue(response.getHeaders().getContentDisposition().isInline());
        assertEquals("使用说明.pdf", response.getHeaders().getContentDisposition().getFilename());
        assertArrayEquals(bytes, response.getBody());
    }

    @Test
    void contentReturnsMarkdownAsUtf8Text() {
        KbService service = mock(KbService.class);
        when(service.content(7L)).thenReturn(new KbService.DocumentContent("规则", "MD", new byte[0]));

        ResponseEntity<byte[]> response = new KbAdminController(service).content(7L);

        assertEquals(MediaType.parseMediaType("text/markdown;charset=UTF-8"),
                response.getHeaders().getContentType());
    }
}
