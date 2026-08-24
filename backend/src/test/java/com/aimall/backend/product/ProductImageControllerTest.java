package com.aimall.backend.product;

import com.aimall.backend.common.GlobalExceptionHandler;
import com.aimall.backend.merchant.ProductImageService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ProductImageControllerTest {
    private final ProductImageService imageService = mock(ProductImageService.class);
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(new ProductImageController(imageService))
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void servesCatalogImageWithMimeAndImmutableCacheHeader() throws Exception {
        String name = "a".repeat(64) + ".webp";
        when(imageService.loadCatalog(name)).thenReturn(new ProductImageService.ImageContent("image/webp", new byte[]{1, 2, 3}));

        mockMvc.perform(get("/api/v1/product-images/catalog/" + name))
                .andExpect(status().isOk())
                .andExpect(content().contentType("image/webp"))
                .andExpect(content().bytes(new byte[]{1, 2, 3}))
                .andExpect(header().string("Cache-Control", "public,max-age=31536000,immutable"));
        verify(imageService).loadCatalog(name);
    }

    @Test
    void catalogRouteIsMoreSpecificThanUuidCatchAll() throws Exception {
        String name = "b".repeat(64) + ".jpg";
        when(imageService.loadCatalog(name)).thenReturn(new ProductImageService.ImageContent("image/jpeg", new byte[]{9}));

        mockMvc.perform(get("/api/v1/product-images/catalog/" + name))
                .andExpect(status().isOk())
                .andExpect(header().string("Content-Type", "image/jpeg"));
        verify(imageService).loadCatalog(name);
    }
}
