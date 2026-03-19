package com.moviesystem.entity;

import lombok.Data;

@Data
public class Movie {
    private Long id;
    private String title;
    private String genres;
    private Integer year;
    private String posterUrl;
}
