package com.aimall.backend.merchant;

import com.aimall.backend.common.BizException;
import com.aimall.backend.config.ObjectStorage;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class ProductImageServiceTest {
    private final ObjectStorage storage = mock(ObjectStorage.class);
    private final ProductImageService service = new ProductImageService(storage);

    @Test
    void uploadsSupportedImageAndReturnsApplicationUrl() throws Exception {
        var file = new MockMultipartFile("file", "phone.webp", "image/webp", new byte[]{1, 2, 3});
        String url = service.upload(file);
        assertTrue(url.matches("/api/v1/product-images/[0-9a-f-]+\\.webp"));
        verify(storage).put(startsWith("product-images/"), any(), eq("image/webp"));
    }

    @Test
    void rejectsUnsupportedFileType() {
        var file = new MockMultipartFile("file", "note.txt", "text/plain", new byte[]{1});
        BizException error = assertThrows(BizException.class, () -> service.upload(file));
        assertEquals("仅支持 JPG、PNG、WebP 图片", error.getMessage());
        verifyNoInteractions(storage);
    }

    @Test
    void rejectsImagesLargerThanFiveMegabytes() {
        var file = new MockMultipartFile("file", "large.png", "image/png", new byte[5 * 1024 * 1024 + 1]);
        BizException error = assertThrows(BizException.class, () -> service.upload(file));
        assertEquals("图片大小不能超过5MB", error.getMessage());
        verifyNoInteractions(storage);
    }
}
