package com.moviesystem.controller;

import com.moviesystem.dto.PageResult;
import com.moviesystem.entity.Movie;
import com.moviesystem.mapper.MovieMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/movies")
@RequiredArgsConstructor
public class MovieController {
    private final MovieMapper movieMapper;

    @GetMapping
    public List<Movie> list(@RequestParam(defaultValue = "1") int page,
                            @RequestParam(defaultValue = "20") int size) {
        int offset = (page - 1) * size;
        return movieMapper.list(offset, size);
    }

    @GetMapping("/{id}")
    public Movie detail(@PathVariable Long id) {
        return movieMapper.getById(id);
    }

    @GetMapping("/page")
    public PageResult<Movie> page(@RequestParam(defaultValue = "1") int page,
                                  @RequestParam(defaultValue = "20") int size) {
        int offset = (page - 1) * size;
        List<Movie> list = movieMapper.list(offset, size);
        long total = movieMapper.countAll();
        return PageResult.of(page, size, total, list);
    }

}
