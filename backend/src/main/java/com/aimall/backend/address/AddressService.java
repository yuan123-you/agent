package com.aimall.backend.address;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Address;
import com.aimall.backend.mapper.AddressMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Stream;

/** 收货地址簿：CRUD + 默认地址解析。 */
@Service
@RequiredArgsConstructor
public class AddressService {

    private final AddressMapper addressMapper;

    public List<Address> list(Long userId) {
        return addressMapper.selectList(new LambdaQueryWrapper<Address>()
                .eq(Address::getUserId, userId)
                .orderByDesc(Address::getIsDefault)
                .orderByDesc(Address::getId));
    }

    public Address defaultFor(Long userId) {
        Address address = addressMapper.selectOne(new LambdaQueryWrapper<Address>()
                .eq(Address::getUserId, userId)
                .eq(Address::getIsDefault, true)
                .orderByDesc(Address::getId)
                .last("LIMIT 1"));
        if (address == null) {
            throw new BizException(2014, "请先在“我的-收货地址”中添加默认收货地址");
        }
        return address;
    }

    @Transactional
    public Address add(Long userId, AddressDtos.AddressRequest req) {
        boolean first = count(userId) == 0;
        Address address = new Address();
        address.setUserId(userId);
        apply(address, req);
        address.setIsDefault(first || Boolean.TRUE.equals(req.getIsDefault()));
        if (!first && Boolean.TRUE.equals(address.getIsDefault())) {
            clearDefault(userId);
        }
        addressMapper.insert(address);
        return address;
    }

    @Transactional
    public void update(Long userId, Long id, AddressDtos.AddressRequest req) {
        Address current = requireOwned(userId, id);
        Address update = new Address();
        update.setId(id);
        apply(update, req);
        if (Boolean.TRUE.equals(req.getIsDefault()) && !Boolean.TRUE.equals(current.getIsDefault())) {
            clearDefault(userId);
            update.setIsDefault(true);
        }
        addressMapper.updateById(update);
    }

    @Transactional
    public void setDefault(Long userId, Long id) {
        requireOwned(userId, id);
        clearDefault(userId);
        Address update = new Address();
        update.setId(id);
        update.setIsDefault(true);
        addressMapper.updateById(update);
    }

    @Transactional
    public void delete(Long userId, Long id) {
        Address address = requireOwned(userId, id);
        addressMapper.deleteById(id);
        if (Boolean.TRUE.equals(address.getIsDefault()) && count(userId) > 0) {
            Address update = new Address();
            update.setId(list(userId).get(0).getId());
            update.setIsDefault(true);
            addressMapper.updateById(update);
        }
    }

    private void apply(Address address, AddressDtos.AddressRequest req) {
        address.setReceiverName(req.getName().trim());
        address.setReceiverPhone(req.getPhone().trim());
        address.setProvince(trim(req.getProvince()));
        address.setCity(trim(req.getCity()));
        address.setDistrict(trim(req.getDistrict()));
        address.setDetailAddress(trim(req.getDetailAddress()));
        String composed = Stream.of(address.getProvince(), address.getCity(), address.getDistrict(), address.getDetailAddress())
                .filter(value -> value != null && !value.isBlank())
                .reduce("", String::concat);
        String legacy = trim(req.getAddress());
        if (composed.isBlank() && legacy != null) composed = legacy;
        if (composed.isBlank()) throw new BizException(2001, "请完整填写收货地址");
        address.setReceiverAddress(composed);
    }

    private void clearDefault(Long userId) {
        addressMapper.update(null, new LambdaUpdateWrapper<Address>()
                .eq(Address::getUserId, userId)
                .set(Address::getIsDefault, false));
    }

    private long count(Long userId) {
        return addressMapper.selectCount(new LambdaQueryWrapper<Address>().eq(Address::getUserId, userId));
    }

    private Address requireOwned(Long userId, Long id) {
        Address address = addressMapper.selectById(id);
        if (address == null || !address.getUserId().equals(userId)) {
            throw new BizException(2002, "地址不存在");
        }
        return address;
    }

    private String trim(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}



