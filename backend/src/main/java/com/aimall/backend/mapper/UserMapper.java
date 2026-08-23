package com.aimall.backend.mapper;

import com.aimall.backend.entity.User;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface UserMapper extends BaseMapper<User> {

    @Select("SELECT COUNT(*) FROM sys_user WHERE deleted=0 AND role<>'ADMIN'")
    long countPlatformUsers();

    @Select("SELECT COUNT(*) FROM sys_user WHERE deleted=0 AND role='MERCHANT'")
    long countMerchants();
}
