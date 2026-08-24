package com.aimall.backend.merchant;

import com.aimall.backend.common.BizException;
import com.aimall.backend.config.ObjectStorage;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ProductImageService {
    private static final long MAX_SIZE = 5L * 1024 * 1024;
    private static final Map<String, String> EXTENSIONS = Map.of(
            "image/jpeg", "jpg",
            "image/png", "png",
            "image/webp", "webp"
    );

    private final ObjectStorage storage;

    public String upload(MultipartFile file) {
        if (file == null || file.isEmpty()) throw new BizException(2001, "请选择要上传的图片");
        String extension = EXTENSIONS.get(file.getContentType());
        if (extension == null) throw new BizException(2001, "仅支持 JPG、PNG、WebP 图片");
        if (file.getSize() > MAX_SIZE) throw new BizException(2001, "图片大小不能超过5MB");
        String filename = UUID.randomUUID() + "." + extension;
        try {
            storage.put("product-images/" + filename, file.getInputStream(), file.getContentType());
        } catch (Exception e) {
            throw new BizException(5002, "图片上传失败，请稍后重试");
        }
        return "/api/v1/product-images/" + filename;
    }

    public ImageContent load(String filename) {
        if (filename == null || !filename.matches("[0-9a-f-]+\\.(jpg|png|webp)")) {
            throw new BizException(2002, "图片不存在");
        }
        try {
            byte[] bytes = storage.get("product-images/" + filename);
            String contentType = filename.endsWith(".png") ? "image/png"
                    : filename.endsWith(".webp") ? "image/webp" : "image/jpeg";
            return new ImageContent(contentType, bytes);
        } catch (Exception e) {
            throw new BizException(2002, "图片不存在");
        }
    }

    public record ImageContent(String contentType, byte[] bytes) {}
}
