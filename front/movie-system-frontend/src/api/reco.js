import http from "./http";

export function getHot(size = 20) {
  return http.get(`/api/hot?size=${size}`);
}

export function getReco(userId, size = 20) {
  return http.get(`/api/reco?userId=${userId}&size=${size}`);
}

export function getMovie(id) {
  return http.get(`/api/movies/${id}`);
}

export function postEvent(payload) {
  return http.post(`/api/event`, payload);
}

export function getHot2(size = 20) {
  return http.get(`/api/hot2?size=${size}`);
}

export function getMoviesPage(page = 1, size = 20) {
  return http.get(`/api/movies/page?page=${page}&size=${size}`);
}
