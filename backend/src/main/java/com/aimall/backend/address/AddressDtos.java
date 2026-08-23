package com.aimall.backend.address;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/** 收货地址请求，兼容旧版整段 address 与新版结构化地区。 */
public class AddressDtos {

    @Data
    public static class AddressRequest {
        @NotBlank
        private String name;
        @NotBlank
        private String phone;
        private String province;
        private String city;
        private String district;
        private String detailAddress;
        /** 旧客户端兼容字段；结构化字段完整时由服务端重新拼接。 */
        private String address;
        private Boolean isDefault;
    }
}
