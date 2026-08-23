package com.aimall.backend.address;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.entity.Address;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 买家收货地址簿：/api/v1/addresses */
@RestController
@RequestMapping("/api/v1/addresses")
@RequiredArgsConstructor
public class AddressController {
    private final AddressService addressService;

    @GetMapping
    public ApiResponse<List<Map<String, Object>>> list(@AuthenticationPrincipal Long userId) {
        return ApiResponse.ok(addressService.list(userId).stream().map(this::toVo).toList());
    }

    @PostMapping
    public ApiResponse<Map<String, Object>> add(@AuthenticationPrincipal Long userId,
                                                @Valid @RequestBody AddressDtos.AddressRequest req) {
        return ApiResponse.ok(toVo(addressService.add(userId, req)));
    }

    @PutMapping("/{id}")
    public ApiResponse<Void> update(@AuthenticationPrincipal Long userId, @PathVariable Long id,
                                    @Valid @RequestBody AddressDtos.AddressRequest req) {
        addressService.update(userId, id, req);
        return ApiResponse.ok();
    }

    @PostMapping("/{id}/default")
    public ApiResponse<Void> setDefault(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        addressService.setDefault(userId, id);
        return ApiResponse.ok();
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        addressService.delete(userId, id);
        return ApiResponse.ok();
    }

    private Map<String, Object> toVo(Address address) {
        Map<String, Object> vo = new LinkedHashMap<>();
        vo.put("addressId", address.getId());
        vo.put("receiverName", address.getReceiverName());
        vo.put("receiverPhone", address.getReceiverPhone());
        vo.put("receiverAddress", address.getReceiverAddress());
        vo.put("province", address.getProvince());
        vo.put("city", address.getCity());
        vo.put("district", address.getDistrict());
        vo.put("detailAddress", address.getDetailAddress());
        vo.put("isDefault", Boolean.TRUE.equals(address.getIsDefault()));
        return vo;
    }
}
