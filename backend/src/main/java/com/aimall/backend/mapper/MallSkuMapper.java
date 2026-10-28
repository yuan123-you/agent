package com.aimall.backend.mapper;

import com.aimall.backend.entity.MallSku;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface MallSkuMapper extends BaseMapper<MallSku> {
    @org.apache.ibatis.annotations.Update("UPDATE mall_sku SET stock = stock + #{delta}, version = version + 1 WHERE id = #{id} AND stock + #{delta} >= 0 " +
            "AND (#{requireOnSale} = FALSE OR (status = 'ENABLE' AND deleted = 0))")
    int adjustAfterSaleStock(@org.apache.ibatis.annotations.Param("id") Long id, @org.apache.ibatis.annotations.Param("delta") int delta,
                            @org.apache.ibatis.annotations.Param("requireOnSale") boolean requireOnSale);

}
