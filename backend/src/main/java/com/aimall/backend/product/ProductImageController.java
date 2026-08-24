package com.aimall.backend.product;

import com.aimall.backend.merchant.ProductImageService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/api/v1/product-images")
@RequiredArgsConstructor
public class ProductImageController {
    private final ProductImageService imageService;

    @GetMapping("/{filename:.+}")
    public ResponseEntity<byte[]> image(@PathVariable String filename) {
        var image = imageService.load(filename);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(image.contentType()))
                .cacheControl(CacheControl.maxAge(30, TimeUnit.DAYS).cachePublic())
                .body(image.bytes());
    }

    @GetMapping("/catalog/{filename:.+}")
    public ResponseEntity<byte[]> catalogImage(@PathVariable String filename) {
        var image = imageService.loadCatalog(filename);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(image.contentType()))
                .header("Cache-Control", "public,max-age=31536000,immutable")
                .body(image.bytes());
    }
}
