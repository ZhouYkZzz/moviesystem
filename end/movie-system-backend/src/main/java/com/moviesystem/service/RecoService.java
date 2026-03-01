package com.moviesystem.service;

import com.moviesystem.dto.RankedMovie;
import com.moviesystem.entity.Movie;

import java.util.List;

public interface RecoService {
    List<Movie> getReco(Long userId, int size);
    List<Movie> getHot(int size);
    void reportEvent(Long userId, Long movieId, String type, Double score);
    List<RankedMovie> getHotRanked(int size);

}
