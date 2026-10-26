package com.aimall.backend.mapper;

import com.aimall.backend.entity.KbDoc;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface KbDocMapper extends BaseMapper<KbDoc> {
    /** Call only within a transaction; serializes ingestion with status/version updates. */
    @Select("SELECT * FROM kb_doc WHERE id = #{id} AND deleted = 0 FOR UPDATE")
    KbDoc selectForUpdate(@Param("id") Long id);
}
