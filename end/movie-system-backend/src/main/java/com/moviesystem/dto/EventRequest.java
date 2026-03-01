package com.moviesystem.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class EventRequest {
    @NotNull
    private Long userId;    // 演示用：前端传 userId（暂不做登录鉴权）
    @NotNull
    private Long movieId;
    @NotNull
    private String type;    // view/fav/rate/click
    private Double score;   // rate 可用
}
