package com.aimall.backend.auth;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Merchant;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.MerchantMapper;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class RegistrationService {

    private final UserMapper userMapper;
    private final MerchantMapper merchantMapper;
    private final PasswordEncoder passwordEncoder;

    public Long registerCustomer(AuthDtos.CustomerRegisterRequest request) {
        return insertUser(request, "CUSTOMER").getId();
    }

    @Transactional
    public Long registerMerchant(AuthDtos.MerchantRegisterRequest request) {
        User user = insertUser(request, "MERCHANT");
        Merchant merchant = new Merchant();
        merchant.setUserId(user.getId());
        merchant.setShopName(request.getShopName().trim());
        merchant.setStatus("ACTIVE");
        merchantMapper.insert(merchant);
        return user.getId();
    }

    private User insertUser(AuthDtos.CustomerRegisterRequest request, String role) {
        String username = request.getUsername().trim();
        Long exists = userMapper.selectCount(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, username));
        if (exists != null && exists > 0) {
            throw new BizException(2005, "用户名已存在");
        }
        User user = new User();
        user.setUsername(username);
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setNickname(request.getNickname().trim());
        user.setPhone(request.getPhone() == null ? null : request.getPhone().trim());
        user.setRole(role);
        user.setStatus("ACTIVE");
        try {
            userMapper.insert(user);
        } catch (DuplicateKeyException exception) {
            throw new BizException(2005, "用户名已存在");
        }
        return user;
    }
}
