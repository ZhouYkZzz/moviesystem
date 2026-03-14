package com.moviesystem.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AuthMapper {
    Long findMaxUserId();

    boolean existsUserId(@Param("userId") Long userId);

    int insertUser(@Param("userId") Long userId);
}
