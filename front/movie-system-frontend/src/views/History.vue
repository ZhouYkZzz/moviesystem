<template>
  <div class="container">
    <div class="topbar">
      <div class="brand">
        <h1>浏览历史</h1>
        <p class="muted">展示用户最近观看过的电影</p>
      </div>

      <div class="controls">
        <router-link class="btn" to="/">← 返回首页</router-link>
      </div>
    </div>

    <div class="section">
      <div v-if="historyList.length === 0" class="empty">
        暂无历史记录
      </div>

      <div class="history-list">
        <div
          class="history-card"
          v-for="item in historyList"
          :key="item.movieId"
          @click="goDetail(item.movieId)"
        >
          <img
            class="history-poster"
            :src="posterOf(item.posterUrl)"
            :alt="`${item.title} 海报`"
            loading="lazy"
            @error="onPosterError"
          />
          <div class="history-meta">
            <h3>{{ item.title }}</h3>
            <p>类型：{{ item.genres }}</p>
            <p>年份：{{ item.year }}</p>
            <p>最近浏览时间：{{ item.eventTime }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { getUserHistory } from '../api/reco'
import { useUserStore } from '../store/user'
import { API_BASE_URL } from '../api/http'

export default {
  name: 'History',
  data() {
    return {
      historyList: []
    }
  },
  async mounted() {
    const userStore = useUserStore()
    const userId = userStore.userId
    const res = await getUserHistory(userId)
    this.historyList = res.data || res || []
  },
  methods: {
    posterOf(url) {
      if (!url) return '/poster-placeholder.svg'
      if (url.startsWith('http://') || url.startsWith('https://')) return url
      return `${API_BASE_URL}${url}`
    },
    onPosterError(event) {
      const img = event?.target
      if (!img || img.dataset.fallback === '1') return
      img.dataset.fallback = '1'
      img.src = '/poster-placeholder.svg'
    },
    goDetail(id) {
      this.$router.push(`/movie/${id}`)
    }
  }
}
</script>

<style scoped>
.history-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 20px;
}

.history-card {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 14px;
  align-items: start;
  border: 1px solid rgba(255,255,255,0.18);
  background: rgba(255,255,255,0.06);
  padding: 16px;
  border-radius: 12px;
  cursor: pointer;
  transition: 0.2s;
}

.history-card:hover {
  background: rgba(255,255,255,0.1);
}

.history-poster {
  width: 100%;
  aspect-ratio: 2 / 3;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid rgba(255,255,255,0.2);
}

.history-meta h3 {
  margin: 0 0 8px;
}

.history-meta p {
  margin: 0 0 5px;
  color: rgba(255,255,255,0.8);
  font-size: 14px;
}

.empty {
  color: #b5bad2;
  margin-top: 20px;
}

@media (max-width: 640px) {
  .history-card {
    grid-template-columns: 1fr;
  }

  .history-poster {
    max-width: 160px;
  }
}
</style>
