package com.moviesystem.mapper;

import com.moviesystem.entity.Movie;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface MovieMapper {
    List<Movie> list(@Param("offset") int offset, @Param("size") int size);
    Movie getById(@Param("id") Long id);
    List<Movie> listByIds(@Param("ids") List<Long> ids);
    int countAll();

}
