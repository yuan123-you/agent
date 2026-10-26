package com.aimall.backend.mapper;

import com.aimall.backend.entity.Address;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface AddressMapper extends BaseMapper<Address> {
    // Lock a stable parent row: an empty address book has no child rows to lock.
    @Select("SELECT id FROM sys_user WHERE id = #{userId} AND deleted = 0 FOR UPDATE")
    Long lockUser(@Param("userId") Long userId);
}