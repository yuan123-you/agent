package com.aimall.backend.merchant;

import jakarta.validation.Validation;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.assertTrue;

class MerchantProductTemplateTest {
    @Test
    void requiresOriginAndShippingLocation() {
        var template = new MerchantController.ProductTemplate();
        template.setName("商品"); template.setBrand("品牌"); template.setCategory("PHONE");
        template.setPrice(BigDecimal.TEN); template.setStock(1); template.setSellingPoints("简介");
        template.setImageUrl("/image.png");
        try (var factory = Validation.buildDefaultValidatorFactory()) {
            var messages = factory.getValidator().validate(template).stream()
                    .map(violation -> violation.getMessage()).toList();
            assertTrue(messages.contains("产地为必填项"));
            assertTrue(messages.contains("发货地为必填项"));
        }
    }
}
