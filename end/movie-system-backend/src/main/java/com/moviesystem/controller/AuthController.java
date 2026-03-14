package com.moviesystem.controller;

import com.moviesystem.dto.LoginRequest;
import com.moviesystem.dto.RegisterRequest;
import com.moviesystem.mapper.AuthMapper;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private static final String DEFAULT_PASSWORD = "123456";
    private static final int MAX_REGISTER_RETRY = 100;

    private final AuthMapper authMapper;

    @PostMapping("/login")
    public ResponseEntity<Map<String, Object>> login(@Valid @RequestBody LoginRequest req) {
        if (!DEFAULT_PASSWORD.equals(req.getPassword())) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("ok", false, "message", "密码错误，默认密码为 123456"));
        }
        if (!authMapper.existsUserId(req.getUserId())) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("ok", false, "message", "用户不存在"));
        }
        return ResponseEntity.ok(Map.of("ok", true, "userId", req.getUserId()));
    }

    @PostMapping("/register")
    public ResponseEntity<Map<String, Object>> register(@RequestBody(required = false) RegisterRequest req) {
        String inputPassword = req == null ? null : req.getPassword();
        if (inputPassword != null && !inputPassword.isBlank() && !DEFAULT_PASSWORD.equals(inputPassword)) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(Map.of("ok", false, "message", "当前系统注册密码固定为 123456"));
        }

        Long currentMax = authMapper.findMaxUserId();
        long maxUserId = currentMax == null ? 0L : currentMax;
        long candidateId = maxUserId + 1;

        for (int i = 0; i < MAX_REGISTER_RETRY; i++) {
            int affected = authMapper.insertUser(candidateId);
            if (affected > 0) {
                return ResponseEntity.ok(Map.of(
                        "ok", true,
                        "userId", candidateId,
                        "defaultPassword", DEFAULT_PASSWORD
                ));
            }
            candidateId++;
        }

        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Map.of("ok", false, "message", "注册失败，请稍后重试"));
    }
}
