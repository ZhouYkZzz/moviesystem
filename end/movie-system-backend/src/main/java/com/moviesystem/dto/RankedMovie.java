package com.moviesystem.dto;

import com.moviesystem.entity.Movie;
import lombok.Data;

@Data
public class RankedMovie {
    private int rank;
    private double hotScore;
    private Movie movie;

    public static RankedMovie of(int rank, double hotScore, Movie movie) {
        RankedMovie r = new RankedMovie();
        r.rank = rank;
        r.hotScore = hotScore;
        r.movie = movie;
        return r;
    }
}
