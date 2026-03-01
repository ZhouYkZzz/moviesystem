package com.moviesystem.entity;

import lombok.Data;

@Data
public class Movie {
    private Long id;
    private String title;
    private String genres;
    private Integer year;
    //private String coverUrl; // 你表里如果没 cover_url，可以先不返回或后续加字段
}
