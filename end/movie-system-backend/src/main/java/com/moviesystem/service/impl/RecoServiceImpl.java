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
    private static final String DELTA_KEY_PREFIX = "reco:user:delta:";
    private static final String RECO_KEY_PREFIX = "reco:user:";
    private static final String USER_RECENT_KEY_PREFIX = "user:recent:";
    private static final String USER_NEG_KEY_PREFIX = "user:neg:";
    private static final String USER_PREF_KEY_PREFIX = "user:pref:genre:";
    private static final String ITEM_LAST_TS_KEY = "item:last_event_ts";

    private static final int OFFLINE_CACHE_HOURS = 24;
    private static final int DELTA_CACHE_MINUTES = 30;
    private static final int RECENT_KEEP_SIZE = 200;

    @Override
    public List<Movie> getReco(Long userId, int size) {
        int targetSize = Math.max(1, size);
        int candidateSize = Math.max(80, targetSize * 4);

        List<Long> offlineIds = loadOfflineIds(userId, candidateSize);
        List<Long> deltaIds = loadDeltaIds(userId, candidateSize);
        List<Long> hotIds = loadHotIds(candidateSize);

        Set<Long> viewedSet = new HashSet<>(userEventMapper.recentViewedMovieIds(userId, 400));
        Set<Long> negativeSet = readLongSet(USER_NEG_KEY_PREFIX + userId);
        Map<String, Double> userGenrePref = loadUserGenrePref(userId);
        long nowEpochSec = System.currentTimeMillis() / 1000;

        LinkedHashSet<Long> merged = new LinkedHashSet<>();
        merged.addAll(offlineIds);
        merged.addAll(deltaIds);
        merged.addAll(hotIds);
        merged.removeAll(negativeSet);

        if (merged.isEmpty()) {
            return getHot(targetSize);
        }

        List<Long> candidateIds = new ArrayList<>(merged);
        List<Movie> candidates = listMoviesByOrderedIds(candidateIds);
        if (candidates.isEmpty()) {
            return getHot(targetSize);
        }

        Map<Long, Integer> offlineRankMap = buildRankMap(offlineIds);
        Map<Long, Integer> deltaRankMap = buildRankMap(deltaIds);

        List<ScoredMovie> scored = new ArrayList<>(candidates.size());
        for (Movie movie : candidates) {
            Long movieId = movie.getId();
            if (movieId == null || negativeSet.contains(movieId)) {
                continue;
            }

            double score = 0.0;
            score += 0.45 * rankScore(offlineRankMap.get(movieId), offlineIds.size());
            score += 0.25 * rankScore(deltaRankMap.get(movieId), deltaIds.size());
            score += 0.15 * popularityScore(movieId);
            score += 0.10 * genreMatchScore(userGenrePref, movie.getGenres());
            score += 0.05 * freshnessScore(movieId, nowEpochSec);

            if (viewedSet.contains(movieId)) {
                score -= 0.60;
            }
            scored.add(new ScoredMovie(movie, score));
        }

        scored.sort((a, b) -> Double.compare(b.score, a.score));

        List<Movie> result = scored.stream()
                .limit(targetSize)
                .map(s -> s.movie)
                .collect(Collectors.toCollection(ArrayList::new));

        if (result.size() < targetSize) {
            Set<Long> picked = result.stream().map(Movie::getId).collect(Collectors.toSet());
            for (Long id : hotIds) {
                if (result.size() >= targetSize) break;
                if (picked.contains(id) || negativeSet.contains(id)) continue;
                Movie m = candidates.stream().filter(x -> id.equals(x.getId())).findFirst().orElse(null);
                if (m != null) {
                    result.add(m);
                    picked.add(id);
                }
            }
        }

        if (result.isEmpty()) {
            return getHot(targetSize);
        }
        return result;
    }

    private List<Long> loadOfflineIds(Long userId, int limit) {
        String cacheKey = RECO_KEY_PREFIX + userId;
        String recoJson = redis.opsForValue().get(cacheKey);

        if (recoJson == null || recoJson.isBlank()) {
            recoJson = userRecoMapper.getRecoJson(userId);
            if (recoJson != null && !recoJson.isBlank()) {
                redis.opsForValue().set(cacheKey, recoJson, OFFLINE_CACHE_HOURS, TimeUnit.HOURS);
            }
        }
        return parseRecoIds(recoJson, limit);
    }

    private List<Long> loadDeltaIds(Long userId, int limit) {
        String deltaKey = DELTA_KEY_PREFIX + userId;
        String deltaJson = redis.opsForValue().get(deltaKey);
        if (deltaJson == null || deltaJson.isBlank()) {
            List<Long> rebuilt = refreshDeltaRecoCache(userId, Math.max(limit, 100));
            deltaJson = toRecoJson(rebuilt);
            redis.opsForValue().set(deltaKey, deltaJson, DELTA_CACHE_MINUTES, TimeUnit.MINUTES);
        }
        return parseRecoIds(deltaJson, limit);
    }

    private List<Long> parseRecoIds(String recoJson, int limit) {
        if (recoJson == null || recoJson.isBlank()) {
            return Collections.emptyList();
        }
        List<Long> ids;
        try {
            ids = objectMapper.readValue(recoJson, new TypeReference<List<Long>>() {});
        } catch (Exception e) {
            return Collections.emptyList();
        }
        LinkedHashSet<Long> uniq = new LinkedHashSet<>(ids);
        return uniq.stream().limit(Math.max(1, limit)).collect(Collectors.toList());
    }

    private String toRecoJson(List<Long> ids) {
        try {
            return objectMapper.writeValueAsString(ids);
        } catch (Exception e) {
            return "[]";
        }
    }

    private List<Long> loadHotIds(int size) {
        Set<ZSetOperations.TypedTuple<String>> tuples =
                redis.opsForZSet().reverseRangeWithScores(HOT_KEY, 0, size - 1);

        List<Long> ids = new ArrayList<>();
        if (tuples != null) {
            for (ZSetOperations.TypedTuple<String> t : tuples) {
                if (t.getValue() != null) {
                    ids.add(Long.valueOf(t.getValue()));
                }
            }
        }

        if (ids.size() < size) {
            List<Movie> fallback = movieMapper.list(0, size * 2);
            Set<Long> exists = new HashSet<>(ids);
            for (Movie m : fallback) {
                if (ids.size() >= size) break;
                if (!exists.contains(m.getId())) {
                    ids.add(m.getId());
                    exists.add(m.getId());
                }
            }
        }
        return ids;
    }

    @Override
    public List<Movie> getHot(int size) {
        List<Long> ids = loadHotIds(Math.max(1, size));
        if (ids.isEmpty()) {
            return Collections.emptyList();
        }
        return listMoviesByOrderedIds(ids);
    }

    private List<Movie> listMoviesByOrderedIds(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return Collections.emptyList();
        }
        List<Movie> movies = movieMapper.listByIds(ids);
        Map<Long, Movie> map = movies.stream().collect(Collectors.toMap(Movie::getId, x -> x, (a, b) -> a));
        List<Movie> ordered = new ArrayList<>();
        for (Long id : ids) {
            Movie m = map.get(id);
            if (m != null) ordered.add(m);
        }
        return ordered;
    }

    @Override
    public void reportEvent(Long userId, Long movieId, String type, Double score) {
        userEventMapper.insert(userId, movieId, type, score, LocalDateTime.now());

        double inc = switch (type) {
            case "view", "click" -> 1.0;
            case "fav" -> 3.0;
            case "rate" -> (score == null ? 1.0 : score);
            default -> 0.5;
        };
        redis.opsForZSet().incrementScore(HOT_KEY, String.valueOf(movieId), inc);

        updateIncrementalCaches(userId, movieId, type, score);
    }

    private void updateIncrementalCaches(Long userId, Long movieId, String type, Double score) {
        long nowEpochSec = System.currentTimeMillis() / 1000;

        String recentKey = USER_RECENT_KEY_PREFIX + userId;
        redis.opsForZSet().add(recentKey, String.valueOf(movieId), nowEpochSec);
        Long card = redis.opsForZSet().zCard(recentKey);
        if (card != null && card > RECENT_KEEP_SIZE) {
            long removeEnd = card - RECENT_KEEP_SIZE - 1;
            redis.opsForZSet().removeRange(recentKey, 0, removeEnd);
        }
        redis.expire(recentKey, 30, TimeUnit.DAYS);

        redis.opsForHash().put(ITEM_LAST_TS_KEY, String.valueOf(movieId), String.valueOf(nowEpochSec));

        String negKey = USER_NEG_KEY_PREFIX + userId;
        if ("rate".equals(type) && score != null && score <= 2.0) {
            redis.opsForSet().add(negKey, String.valueOf(movieId));
            redis.expire(negKey, 30, TimeUnit.DAYS);
        } else if ("fav".equals(type) || ("rate".equals(type) && score != null && score >= 4.0)) {
            redis.opsForSet().remove(negKey, String.valueOf(movieId));
        }

        double prefBoost = preferenceBoost(type, score);
        if (prefBoost != 0.0) {
            Movie movie = movieMapper.getById(movieId);
            if (movie != null) {
                String prefKey = USER_PREF_KEY_PREFIX + userId;
                for (String genre : parseGenres(movie.getGenres())) {
                    redis.opsForHash().increment(prefKey, genre, prefBoost);
                }
                redis.expire(prefKey, 30, TimeUnit.DAYS);
            }
        }

        List<Long> delta = refreshDeltaRecoCache(userId, 100);
        String deltaKey = DELTA_KEY_PREFIX + userId;
        redis.opsForValue().set(deltaKey, toRecoJson(delta), DELTA_CACHE_MINUTES, TimeUnit.MINUTES);
    }

    private double preferenceBoost(String type, Double score) {
        return switch (type) {
            case "view" -> 0.12;
            case "click" -> 0.08;
            case "fav" -> 0.90;
            case "rate" -> {
                if (score == null) {
                    yield 0.0;
                }
                if (score >= 4.0) {
                    yield 0.80;
                }
                if (score <= 2.0) {
                    yield -0.60;
                }
                yield 0.10;
            }
            default -> 0.0;
        };
    }

    private List<Long> refreshDeltaRecoCache(Long userId, int topN) {
        int target = Math.max(20, topN);
        Map<String, Double> prefMap = loadUserGenrePref(userId);
        Set<Long> negativeSet = readLongSet(USER_NEG_KEY_PREFIX + userId);
        Set<Long> viewedSet = new HashSet<>(recentViewedIds(userId, 80));

        if (prefMap.isEmpty() && viewedSet.isEmpty()) {
            return loadHotIds(target).stream()
                    .filter(id -> !negativeSet.contains(id))
                    .limit(target)
                    .collect(Collectors.toList());
        }

        List<Movie> allMovies = movieMapper.list(0, 5000);
        long nowEpochSec = System.currentTimeMillis() / 1000;

        List<ScoredId> scored = new ArrayList<>(allMovies.size());
        for (Movie movie : allMovies) {
            Long movieId = movie.getId();
            if (movieId == null || viewedSet.contains(movieId) || negativeSet.contains(movieId)) {
                continue;
            }
            double genre = genreMatchScore(prefMap, movie.getGenres());
            double pop = popularityScore(movieId);
            double fresh = freshnessScore(movieId, nowEpochSec);
            double total = 0.65 * genre + 0.25 * pop + 0.10 * fresh;
            scored.add(new ScoredId(movieId, total));
        }

        scored.sort((a, b) -> Double.compare(b.score, a.score));
        return scored.stream().limit(target).map(s -> s.id).collect(Collectors.toList());
    }

    private List<Long> recentViewedIds(Long userId, int limit) {
        String recentKey = USER_RECENT_KEY_PREFIX + userId;
        Set<String> recent = redis.opsForZSet().reverseRange(recentKey, 0, limit - 1);
        List<Long> ids = new ArrayList<>();
        if (recent != null) {
            for (String id : recent) {
                ids.add(Long.valueOf(id));
            }
        }
        if (!ids.isEmpty()) {
            return ids;
        }
        return userEventMapper.recentViewedMovieIds(userId, limit);
    }

    private Set<Long> readLongSet(String key) {
        Set<String> members = redis.opsForSet().members(key);
        if (members == null || members.isEmpty()) {
            return Collections.emptySet();
        }
        Set<Long> out = new HashSet<>(members.size());
        for (String v : members) {
            out.add(Long.valueOf(v));
        }
        return out;
    }

    private Map<String, Double> loadUserGenrePref(Long userId) {
        String prefKey = USER_PREF_KEY_PREFIX + userId;
        Map<Object, Object> raw = redis.opsForHash().entries(prefKey);
        if (raw == null || raw.isEmpty()) {
            return Collections.emptyMap();
        }
        Map<String, Double> map = new HashMap<>();
        for (Map.Entry<Object, Object> e : raw.entrySet()) {
            map.put(String.valueOf(e.getKey()).toLowerCase(Locale.ROOT), Double.parseDouble(String.valueOf(e.getValue())));
        }
        return map;
    }

    private List<String> parseGenres(String genres) {
        if (genres == null || genres.isBlank()) {
            return Collections.emptyList();
        }
        return Arrays.stream(genres.split("\\|"))
                .map(x -> x.trim().toLowerCase(Locale.ROOT))
                .filter(x -> !x.isBlank())
                .collect(Collectors.toList());
    }

    private double genreMatchScore(Map<String, Double> prefMap, String genres) {
        if (prefMap.isEmpty()) {
            return 0.0;
        }
        double sum = 0.0;
        for (String g : parseGenres(genres)) {
            sum += prefMap.getOrDefault(g, 0.0);
        }
        return Math.tanh(sum / 3.0);
    }

    private double popularityScore(Long movieId) {
        Double hot = redis.opsForZSet().score(HOT_KEY, String.valueOf(movieId));
        if (hot == null || hot <= 0) {
            return 0.0;
        }
        return Math.log1p(hot);
    }

    private double freshnessScore(Long movieId, long nowEpochSec) {
        Object raw = redis.opsForHash().get(ITEM_LAST_TS_KEY, String.valueOf(movieId));
        if (raw == null) {
            return 0.0;
        }
        long ts;
        try {
            ts = Long.parseLong(String.valueOf(raw));
        } catch (NumberFormatException e) {
            return 0.0;
        }
        double ageHours = Math.max(0.0, (nowEpochSec - ts) / 3600.0);
        return Math.exp(-ageHours / 72.0);
    }

    private Map<Long, Integer> buildRankMap(List<Long> ids) {
        Map<Long, Integer> map = new HashMap<>();
        for (int i = 0; i < ids.size(); i++) {
            map.putIfAbsent(ids.get(i), i);
        }
        return map;
    }

    private double rankScore(Integer index, int total) {
        if (index == null || total <= 0) {
            return 0.0;
        }
        double denom = Math.max(1.0, total - 1.0);
        return 1.0 - (index / denom);
    }

    @Override
    public List<RankedMovie> getHotRanked(int size) {
        Set<ZSetOperations.TypedTuple<String>> tuples =
                redis.opsForZSet().reverseRangeWithScores(HOT_KEY, 0, size - 1);

        if (tuples == null || tuples.isEmpty()) {
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

    private static class ScoredMovie {
        private final Movie movie;
        private final double score;

        private ScoredMovie(Movie movie, double score) {
            this.movie = movie;
            this.score = score;
        }
    }

    private static class ScoredId {
        private final Long id;
        private final double score;

        private ScoredId(Long id, double score) {
            this.id = id;
            this.score = score;
        }
    }

}
