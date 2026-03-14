<template>
  <div class="container">
    <div class="topbar">
      <div class="brand">
        <h1>Movie System · BERT4Rec</h1>
        <p>个性化推荐（Redis/MySQL） + 热门榜（Redis ZSET） + 全部电影分页</p>
      </div>

      <div class="controls">
        <span class="muted">当前用户ID：{{ userStore.userId }}</span>
        <button class="btn" @click="reloadAll">刷新</button>
        <button class="btn" @click="$router.push('/history')">浏览历史</button>
        <button class="btn" @click="switchUser">切换用户</button>
      </div>

    </div>

    <!-- 个性化推荐 -->
    <div class="section">
      <div class="section-head">
        <h2 class="section-title">个性化推荐</h2>
        <p class="section-sub">userId = {{ userStore.userId }} · size = 20</p>
      </div>

      <div v-if="reco.length === 0" class="muted">暂无推荐（会自动用热门兜底）</div>

      <div class="grid">
        <router-link
          v-for="(m, idx) in reco"
          :key="m.id"
          class="card"
          :to="`/movie/${m.id}`"
        >
          <div class="rank">NO.{{ idx + 1 }}</div>
          <p class="card-title">{{ m.title }}</p>
          <div class="badges">
            <span class="badge">{{ m.year || "----" }}</span>
            <span class="badge">{{ m.genres }}</span>
            <span class="badge-heat">热度 {{ heatMap[m.id] ?? 0 }}</span>
          </div>
        </router-link>
      </div>
    </div>

    <!-- 热门榜（带热度） -->
    <div class="section">
      <div class="section-head">
        <h2 class="section-title">热门榜</h2>
        <p class="section-sub">点击详情页会自动上报 view / fav / rate，热度会变化</p>
      </div>

      <div class="grid">
        <router-link
          v-for="(x, idx) in hotRanked"
          :key="x.movie.id"
          class="card"
          :to="`/movie/${x.movie.id}`"
        >
          <div class="rank">NO.{{ idx + 1 }}</div>
          <p class="card-title">{{ x.movie.title }}</p>
          <div class="badges">
            <span class="badge">{{ x.movie.year || "----" }}</span>
            <span class="badge">{{ x.movie.genres }}</span>
            <span class="badge-heat">热度 {{ formatHeat(x.hotScore) }}</span>
          </div>
        </router-link>
      </div>
    </div>

    <!-- 全部电影（分页） -->
    <div class="section">
      <div class="section-head">
        <h2 class="section-title">全部电影</h2>
        <p class="section-sub">分页浏览 · 每页 20 部 · 总数 {{ totalMovies }}</p>
      </div>

      <div class="controls" style="justify-content: flex-start;">
        <button class="btn" :disabled="page <= 1" @click="prevPage">上一页</button>
        <span class="muted">第 {{ page }} 页 / 共 {{ totalPages }} 页</span>
        <button class="btn" :disabled="page >= totalPages" @click="nextPage">下一页</button>
        <button class="btn" @click="goFirst">回到第一页</button>
      </div>

      <div class="grid" style="margin-top: 12px;">
        <router-link
          v-for="(m, idx) in moviesPage"
          :key="m.id"
          class="card"
          :to="`/movie/${m.id}`"
        >
          <div class="rank">#{{ (page - 1) * pageSize + idx + 1 }}</div>
          <p class="card-title">{{ m.title }}</p>
          <div class="badges">
            <span class="badge">{{ m.year || "----" }}</span>
            <span class="badge">{{ m.genres }}</span>
            <span class="badge-heat">热度 {{ heatMap[m.id] ?? 0 }}</span>
          </div>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "../store/user";
import { getHot2, getReco, getMoviesPage } from "../api/reco";

const userStore = useUserStore();
const router = useRouter();

const reco = ref([]);
const hotRanked = ref([]);

// heatMap: movieId -> hotScore（用于个性化推荐/全部电影显示热度）
const heatMap = ref({});

function formatHeat(x) {
  // 热度显示更“明显”
  if (x == null) return 0;
  return Math.round(x * 10) / 10;
}

async function loadReco() {
  const res = await getReco(userStore.userId, 20);
  reco.value = Array.isArray(res.data) ? res.data : [];
}

async function loadHot() {
  const res = await getHot2(20);
  hotRanked.value = Array.isArray(res.data) ? res.data : [];

  // 更新 heatMap（让其它区域也能显示热度）
  const map = {};
  for (const item of hotRanked.value) {
    if (item?.movie?.id != null) map[item.movie.id] = formatHeat(item.hotScore);
  }
  heatMap.value = map;
}

async function reloadAll() {
  await Promise.all([loadReco(), loadHot(), loadMovies()]);
}

function switchUser() {
  userStore.logout();
  router.push("/login");
}

// ======= 全部电影分页 =======
const page = ref(1);
const pageSize = 20;
const totalMovies = ref(0);
const moviesPage = ref([]);

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(totalMovies.value / pageSize));
});

async function loadMovies() {
  const res = await getMoviesPage(page.value, pageSize);
  const data = res.data || {};
  moviesPage.value = Array.isArray(data.list) ? data.list : [];
  totalMovies.value = Number(data.total || 0);
}

async function prevPage() {
  if (page.value <= 1) return;
  page.value -= 1;
  await loadMovies();
}

async function nextPage() {
  if (page.value >= totalPages.value) return;
  page.value += 1;
  await loadMovies();
}

async function goFirst() {
  page.value = 1;
  await loadMovies();
}

onMounted(reloadAll);
</script>
