package com.aimall.backend.common;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.AllArgsConstructor;
import lombok.Data;

import java.util.List;
import java.util.function.Function;

/**
 * 统一分页响应结构
 */
@Data
@AllArgsConstructor
public class PageResult<T> {

    private List<T> records;
    private long total;
    private long page;
    private long size;

    public static <E, T> PageResult<T> of(Page<E> p, Function<E, T> mapper) {
        return new PageResult<>(p.getRecords().stream().map(mapper).toList(),
                p.getTotal(), p.getCurrent(), p.getSize());
    }

    public static <T> PageResult<T> of(Page<T> p) {
        return new PageResult<>(p.getRecords(), p.getTotal(), p.getCurrent(), p.getSize());
    }
}
