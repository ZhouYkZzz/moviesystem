package com.moviesystem.service.impl;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moviesystem.dto.RankedMovie;
import com.moviesystem.entity.Movie;
import com.moviesystem.mapper.MovieMapper;
import com.moviesystem.mapper.UserEventMapper;
import com.moviesystem.mapper.UserRecoMapper;
import com.moviesystem.service.RecoService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class RecoServiceImpl implements RecoService {

    private final StringRedisTemplate redis;
    private final MovieMapper movieMapper;
    private final UserRecoMapper userRecoMapper;
    private final UserEventMapper userEventMapper;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private static final String HOT_KEY = "hot:movies";
    private static final String RECO_KEY_PREFIX = "reco:user:";

    @Override
    public List<Movie> getReco(Long userId, int size) {
        // 1) 先从 Redis 拿
        String cacheKey = RECO_KEY_PREFIX + userId;
        String recoJson = redis.opsForValue().get(cacheKey);

        // 2) Redis miss -> MySQL user_reco
        if (recoJson == null || recoJson.isBlank()) {
            recoJson = userRecoMapper.getRecoJson(userId);
            if (recoJson != null && !recoJson.isBlank()) {
                redis.opsForValue().set(cacheKey, recoJson, 24, TimeUnit.HOURS);
            }
        }

        // 3) 仍 miss -> 热门兜底
        List<Long> ids;
        if (recoJson == null || recoJson.isBlank()) {
            return getHot(size);
        }

        try {
            ids = objectMapper.readValue(recoJson, new TypeReference<List<Long>>() {});
        } catch (Exception e) {
            return getHot(size);
        }

        // 4) 去重：过滤用户最近看过的（可选但很加分）
        List<Long> viewed = userEventMapper.recentViewedMovieIds(userId, 200);
        Set<Long> viewedSet = new HashSet<>(viewed);

        List<Long> filtered = ids.stream()
                .filter(id -> !viewedSet.contains(id))
                .limit(size)
                .collect(Collectors.toList());

        // 不足补热门
        if (filtered.size() < size) {
            List<Movie> hot = getHot(size);
            Set<Long> already = new HashSet<>(filtered);
            for (Movie m : hot) {
                if (filtered.size() >= size) break;
                if (!already.contains(m.getId())) filtered.add(m.getId());
            }
        }

        // 5) 批量查 movie 信息，保持顺序
        List<Movie> movies = movieMapper.listByIds(filtered);
        Map<Long, Movie> map = movies.stream().collect(Collectors.toMap(Movie::getId, x -> x));
        List<Movie> ordered = new ArrayList<>();
        for (Long id : filtered) {
            Movie m = map.get(id);
            if (m != null) ordered.add(m);
        }
        return ordered;
    }

    @Override
    public List<Movie> getHot(int size) {
        Set<ZSetOperations.TypedTuple<String>> tuples =
                redis.opsForZSet().reverseRangeWithScores(HOT_KEY, 0, size - 1);

        List<Long> ids = new ArrayList<>();
        if (tuples != null) {
            for (ZSetOperations.TypedTuple<String> t : tuples) {
                if (t.getValue() != null) ids.add(Long.valueOf(t.getValue()));
            }
        }

        // 如果 hot:movies 不足 size（比如只有1条），就用 movie 表补齐
        if (ids.size() < size) {
            int need = size - ids.size();
            List<Movie> fallback = movieMapper.list(0, size * 2); // 多取点，方便去重
            Set<Long> exist = new HashSet<>(ids);
            for (Movie m : fallback) {
                if (ids.size() >= size) break;
                if (!exist.contains(m.getId())) {
                    ids.add(m.getId());
                    exist.add(m.getId());
                }
            }
        }

        if (ids.isEmpty()) {
            return Collections.emptyList();
        }

        // 批量查 movie 信息，保持顺序
        List<Movie> movies = movieMapper.listByIds(ids);
        Map<Long, Movie> map = movies.stream().collect(Collectors.toMap(Movie::getId, x -> x));
        List<Movie> ordered = new ArrayList<>();
        for (Long id : ids) {
            Movie m = map.get(id);
            if (m != null) ordered.add(m);
        }
        return ordered;
    }


    @Override
    public void reportEvent(Long userId, Long movieId, String type, Double score) {
        // 1) 写 MySQL
        userEventMapper.insert(userId, movieId, type, score, LocalDateTime.now());

        // 2) 更新热门榜
        double inc = switch (type) {
            case "view", "click" -> 1.0;
            case "fav" -> 3.0;
            case "rate" -> (score == null ? 1.0 : score); // 评分越高热度加得越多
            default -> 0.5;
        };
        redis.opsForZSet().incrementScore(HOT_KEY, String.valueOf(movieId), inc);
    }

    @Override
    public List<RankedMovie> getHotRanked(int size) {
        Set<ZSetOperations.TypedTuple<String>> tuples =
                redis.opsForZSet().reverseRangeWithScores(HOT_KEY, 0, size - 1);

        // 没有热门数据就返回空，让前端自己 fallback 或你也可以补齐
        if (tuples == null || tuples.isEmpty()) {
            // 你也可以选择补齐：用 movieMapper.list(...) 并 hotScore=0
            List<Movie> fallback = movieMapper.list(0, size);
            List<RankedMovie> res = new ArrayList<>();
            for (int i = 0; i < fallback.size(); i++) {
                res.add(RankedMovie.of(i + 1, 0.0, fallback.get(i)));
            }
            return res;
        }

        List<Long> ids = new ArrayList<>();
        List<Double> scores = new ArrayList<>();
        for (ZSetOperations.TypedTuple<String> t : tuples) {
            if (t.getValue() == null) continue;
            ids.add(Long.valueOf(t.getValue()));
            scores.add(t.getScore() == null ? 0.0 : t.getScore());
        }

        // 不足 size 就用 movie 表补齐（hotScore=0）
        if (ids.size() < size) {
            int need = size - ids.size();
            List<Movie> fallback = movieMapper.list(0, size * 2);
            Set<Long> exist = new HashSet<>(ids);
            for (Movie m : fallback) {
                if (need <= 0) break;
                if (!exist.contains(m.getId())) {
                    ids.add(m.getId());
                    scores.add(0.0);
                    exist.add(m.getId());
                    need--;
                }
            }
        }

        List<Movie> movies = movieMapper.listByIds(ids);
        Map<Long, Movie> map = movies.stream().collect(Collectors.toMap(Movie::getId, x -> x));

        List<RankedMovie> res = new ArrayList<>();
        for (int i = 0; i < ids.size(); i++) {
            Movie m = map.get(ids.get(i));
            if (m != null) {
                res.add(RankedMovie.of(i + 1, scores.get(i), m));
            }
        }
        return res;
    }

}
