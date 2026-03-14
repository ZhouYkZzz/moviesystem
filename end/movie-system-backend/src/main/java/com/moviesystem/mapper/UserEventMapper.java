package com.moviesystem.mapper;

import com.moviesystem.dto.HistoryDTO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;

@Mapper
public interface UserEventMapper {
    int insert(@Param("userId") Long userId,
               @Param("movieId") Long movieId,
               @Param("eventType") String eventType,
               @Param("score") Double score,
               @Param("eventTime") LocalDateTime eventTime);
    List<HistoryDTO> getUserHistory(@Param("userId") Long userId);

    List<Long> recentViewedMovieIds(@Param("userId") Long userId, @Param("limit") int limit);
}
