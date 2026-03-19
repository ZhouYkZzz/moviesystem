<template>
  <div class="container">
    <div class="topbar">
      <div class="brand">
        <h1>电影详情</h1>
        <p class="muted">进入页面自动上报 view（影响热门榜）</p>
      </div>
      <div class="controls">
        <router-link class="btn" to="/">← 返回首页</router-link>
      </div>
    </div>

    <div class="section">
      <div v-if="!movie" class="muted">加载中...</div>

      <div v-else class="detail-layout">
        <div class="detail-poster-wrap">
          <img
            class="detail-poster"
            :src="posterOf(movie.posterUrl)"
            :alt="`${movie.title} 海报`"
            loading="lazy"
            @error="onPosterError"
          />
        </div>

        <div>
          <h2 style="margin: 0 0 6px 0;">{{ movie.title }}</h2>
          <div class="badges" style="margin-bottom: 14px;">
            <span class="badge">Year: {{ movie.year || "----" }}</span>
            <span class="badge">{{ movie.genres }}</span>
            <span class="badge">User: {{ userStore.userId }}</span>
          </div>

          <div class="controls" style="justify-content: flex-start;">
            <button class="btn" @click="fav">收藏</button>
            <select class="input" v-model.number="ratingScore" style="min-width: 100px;">
              <option v-for="s in [1, 2, 3, 4, 5]" :key="s" :value="s">{{ s }} 分</option>
            </select>
            <button class="btn" @click="rateMovie">评分</button>
            <button class="btn" @click="viewAgain">观看（+热度）</button>
          </div>

          <p class="muted" style="margin-top: 14px;">
            小提示：回到首页点“刷新”，热门榜会变化。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { useUserStore } from "../store/user";
import { getMovie, postEvent } from "../api/reco";
import { API_BASE_URL } from "../api/http";

const route = useRoute();
const userStore = useUserStore();
const movie = ref(null);
const ratingScore = ref(5);
const FALLBACK_POSTER = "/poster-placeholder.svg";

function posterOf(url) {
  if (!url) return FALLBACK_POSTER;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${API_BASE_URL}${url}`;
}

function onPosterError(event) {
  const img = event?.target;
  if (!img || img.dataset.fallback === "1") return;
  img.dataset.fallback = "1";
  img.src = FALLBACK_POSTER;
}

async function load() {
  const id = Number(route.params.id);
  const res = await getMovie(id);
  movie.value = res.data;

  await postEvent({ userId: userStore.userId, movieId: id, type: "view" });
}

async function viewAgain() {
  const id = Number(route.params.id);
  await postEvent({ userId: userStore.userId, movieId: id, type: "view" });
  alert("已上报 view（热门热度+1）");
}

async function fav() {
  const id = Number(route.params.id);
  await postEvent({ userId: userStore.userId, movieId: id, type: "fav" });
  alert("已收藏（热门热度+3）");
}

async function rateMovie() {
  const id = Number(route.params.id);
  await postEvent({ userId: userStore.userId, movieId: id, type: "rate", score: ratingScore.value });
  alert(`已评分 ${ratingScore.value} 分`);
}

onMounted(load);
</script>

<style scoped>
.detail-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 18px;
  align-items: start;
}

.detail-poster-wrap {
  width: 100%;
  aspect-ratio: 2 / 3;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.18);
  background: rgba(255,255,255,0.06);
}

.detail-poster {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

@media (max-width: 760px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }

  .detail-poster-wrap {
    max-width: 260px;
  }
}
</style>
