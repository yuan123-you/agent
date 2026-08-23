package com.aimall.backend.product;

import com.aimall.backend.merchant.MerchantController;
import org.junit.jupiter.api.Test;
import org.springframework.web.bind.annotation.PutMapping;

import java.lang.reflect.Method;
import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AdminProductContractTest {

    @Test
    void adminProductsExposeNoUpdateContract() {
        assertFalse(Arrays.stream(AdminProductController.class.getDeclaredMethods())
                .anyMatch(method -> method.isAnnotationPresent(PutMapping.class)));
        assertThrows(NoSuchMethodException.class, () -> ProductService.class.getDeclaredMethod(
                "update", Long.class, ProductService.ProductSaveRequest.class));
    }

    @Test
    void merchantProductsKeepOwnedUpdateContract() {
        Method update = Arrays.stream(MerchantController.class.getDeclaredMethods())
                .filter(method -> method.getName().equals("update"))
                .findFirst()
                .orElseThrow();
        PutMapping mapping = update.getAnnotation(PutMapping.class);
        assertTrue(mapping != null && Arrays.asList(mapping.value()).contains("/products/{id}"));
    }
}
