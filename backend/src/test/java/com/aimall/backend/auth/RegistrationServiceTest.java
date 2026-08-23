package com.aimall.backend.auth;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.MerchantMapper;
import com.aimall.backend.mapper.UserMapper;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.password.PasswordEncoder;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.*;

class RegistrationServiceTest {

    private final UserMapper userMapper = mock(UserMapper.class);
    private final MerchantMapper merchantMapper = mock(MerchantMapper.class);
    private final PasswordEncoder passwordEncoder = mock(PasswordEncoder.class);
    private final RegistrationService service = new RegistrationService(userMapper, merchantMapper, passwordEncoder);

    @Test
    void registersCustomerAsActiveCustomer() {
        when(userMapper.selectCount(any())).thenReturn(0L);
        when(passwordEncoder.encode("123456")).thenReturn("hashed-password");
        when(userMapper.insert(any(User.class))).thenAnswer(i -> { i.<User>getArgument(0).setId(11L); return 1; });

        service.registerCustomer(customerRequest(" buyer01 "));

        verify(userMapper).insert(argThat((User u) -> "buyer01".equals(u.getUsername())
                && "hashed-password".equals(u.getPassword())
                && "CUSTOMER".equals(u.getRole())
                && "ACTIVE".equals(u.getStatus())));
    }

    @Test
    void registersMerchantAndShopTogether() {
        when(userMapper.selectCount(any())).thenReturn(0L);
        when(userMapper.insert(any(User.class))).thenAnswer(i -> { i.<User>getArgument(0).setId(12L); return 1; });
        service.registerMerchant(merchantRequest("seller01", "源选店"));
        verify(userMapper).insert(argThat((User u) -> "MERCHANT".equals(u.getRole())));
        verify(merchantMapper).insert(argThat((com.aimall.backend.entity.Merchant m) -> m.getUserId() == 12L && "源选店".equals(m.getShopName()) && "ACTIVE".equals(m.getStatus())));
    }

    @Test
    void rejectsDuplicateUsername() {
        when(userMapper.selectCount(any())).thenReturn(1L);
        assertThatThrownBy(() -> service.registerCustomer(customerRequest("buyer01")))
                .isInstanceOf(BizException.class).hasMessageContaining("用户名已存在");
        verify(userMapper, never()).insert(any(User.class));
    }

    private static AuthDtos.CustomerRegisterRequest customerRequest(String username) {
        AuthDtos.CustomerRegisterRequest request = new AuthDtos.CustomerRegisterRequest();
        request.setUsername(username);
        request.setPassword("123456");
        request.setNickname("买家");
        request.setPhone("13800000000");
        return request;
    }

    private static AuthDtos.MerchantRegisterRequest merchantRequest(String username, String shopName) {
        AuthDtos.MerchantRegisterRequest request = new AuthDtos.MerchantRegisterRequest();
        request.setUsername(username);
        request.setPassword("123456");
        request.setNickname("店主");
        request.setShopName(shopName);
        return request;
    }
}
