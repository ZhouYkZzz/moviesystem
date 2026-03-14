package com.moviesystem.controller;

import com.moviesystem.dto.EventRequest;
import com.moviesystem.dto.HistoryDTO;
import com.moviesystem.mapper.UserEventMapper;
import com.moviesystem.service.RecoService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class EventController {

    private final RecoService recoService;
    @Autowired
    private UserEventMapper userEventMapper;


    @PostMapping("/event")
    public Map<String, Object> report(@Valid @RequestBody EventRequest req) {
        recoService.reportEvent(req.getUserId(), req.getMovieId(), req.getType(), req.getScore());
        return Map.of("ok", true);
    }
    @GetMapping("/history")
    public List<HistoryDTO> getHistory(@RequestParam("userId") Long userId) {
        return userEventMapper.getUserHistory(userId);
    }

}
