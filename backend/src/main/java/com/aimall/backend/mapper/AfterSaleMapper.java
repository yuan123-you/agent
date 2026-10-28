package com.aimall.backend.mapper;

import com.aimall.backend.entity.AfterSale;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AfterSaleMapper extends BaseMapper<AfterSale> {
    @org.apache.ibatis.annotations.Select("SELECT * FROM after_sale WHERE id = #{id} FOR UPDATE")
    AfterSale selectForUpdate(@org.apache.ibatis.annotations.Param("id") Long id);
}
