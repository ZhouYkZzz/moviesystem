package com.moviesystem.controller;

import com.moviesystem.dto.RankedMovie;
import com.moviesystem.entity.Movie;
import com.moviesystem.service.RecoService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class RecoController {

    private final RecoService recoService;

    @GetMapping("/reco")
    public List<Movie> reco(@RequestParam Long userId,
                            @RequestParam(defaultValue = "20") int size) {
        return recoService.getReco(userId, size);
    }

    @GetMapping("/hot")
    public List<Movie> hot(@RequestParam(defaultValue = "20") int size) {
        return recoService.getHot(size);
    }
    @GetMapping("/hot2")
    public List<RankedMovie> hot2(@RequestParam(defaultValue = "20") int size) {
        return recoService.getHotRanked(size);
    }

}
