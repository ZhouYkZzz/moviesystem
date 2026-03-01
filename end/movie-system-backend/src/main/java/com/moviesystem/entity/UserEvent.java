package com.moviesystem.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class UserEvent {
    private Long id;
    private Long userId;
    private Long movieId;
    private String eventType; // view/rate/fav/click
    private Double score;
    private LocalDateTime eventTime;
}
