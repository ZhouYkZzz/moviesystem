package com.moviesystem.dto;

import lombok.Data;
import java.util.List;

@Data
public class PageResult<T> {
    private int page;
    private int size;
    private long total;
    private List<T> list;

    public static <T> PageResult<T> of(int page, int size, long total, List<T> list) {
        PageResult<T> r = new PageResult<>();
        r.page = page;
        r.size = size;
        r.total = total;
        r.list = list;
        return r;
    }
}
