package com.moviesystem.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface UserRecoMapper {
    String getRecoJson(@Param("userId") Long userId);
}
