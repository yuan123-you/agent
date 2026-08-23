package com.aimall.backend.address;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Address;
import com.aimall.backend.mapper.AddressMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class AddressServiceTest {
    private final AddressMapper mapper = mock(AddressMapper.class);
    private final AddressService service = new AddressService(mapper);

    @Test
    void addComposesStructuredAddressAndMakesFirstAddressDefault() {
        when(mapper.selectCount(any())).thenReturn(0L);
        var request = structuredRequest();

        Address saved = service.add(7L, request);

        assertEquals("浙江省", saved.getProvince());
        assertEquals("杭州市", saved.getCity());
        assertEquals("西湖区", saved.getDistrict());
        assertEquals("文三路 90 号", saved.getDetailAddress());
        assertEquals("浙江省杭州市西湖区文三路 90 号", saved.getReceiverAddress());
        assertTrue(saved.getIsDefault());
        verify(mapper).insert(saved);
    }

    @Test
    void defaultForReturnsSavedDefaultAddress() {
        Address expected = new Address();
        expected.setId(12L);
        expected.setUserId(7L);
        expected.setIsDefault(true);
        when(mapper.selectOne(any())).thenReturn(expected);

        assertSame(expected, service.defaultFor(7L));
    }

    @Test
    void defaultForRejectsUserWithoutSavedAddress() {
        when(mapper.selectOne(any())).thenReturn(null);

        BizException error = assertThrows(BizException.class, () -> service.defaultFor(7L));

        assertEquals(2014, error.getCode());
        assertTrue(error.getMessage().contains("默认收货地址"));
    }

    private AddressDtos.AddressRequest structuredRequest() {
        var request = new AddressDtos.AddressRequest();
        request.setName("张三");
        request.setPhone("13800138000");
        request.setProvince("浙江省");
        request.setCity("杭州市");
        request.setDistrict("西湖区");
        request.setDetailAddress("文三路 90 号");
        request.setIsDefault(false);
        return request;
    }
}
