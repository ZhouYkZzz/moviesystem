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

      <div v-else>
        <h2 style="margin: 0 0 6px 0;">{{ movie.title }}</h2>
        <div class="badges" style="margin-bottom: 14px;">
          <span class="badge">Year: {{ movie.year || "----" }}</span>
          <span class="badge">{{ movie.genres }}</span>
          <span class="badge">User: {{ userStore.userId }}</span>
        </div>

        <div class="controls" style="justify-content: flex-start;">
          <button class="btn" @click="fav">收藏</button>
          <button class="btn" @click="rate5">点赞</button>
          <button class="btn" @click="viewAgain">观看（+热度）</button>
        </div>

        <p class="muted" style="margin-top: 14px;">
          小提示：回到首页点“刷新”，热门榜会变化。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import { useUserStore } from "../store/user";
import { getMovie, postEvent } from "../api/reco";

const route = useRoute();
const userStore = useUserStore();
const movie = ref(null);

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

async function rate5() {
  const id = Number(route.params.id);
  await postEvent({ userId: userStore.userId, movieId: id, type: "rate", score: 5.0 });
  alert("已点赞（热门热度+5）");
}

onMounted(load);
</script>
