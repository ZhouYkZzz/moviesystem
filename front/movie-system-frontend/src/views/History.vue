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
          <h3>{{ item.title }}</h3>
          <p>类型：{{ item.genres }}</p>
          <p>年份：{{ item.year }}</p>
          <p>最近浏览时间：{{ item.eventTime }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { getUserHistory } from '../api/reco'
import { useUserStore } from '../store/user'

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
  border: 1px solid #ddd;
  padding: 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: 0.2s;
}

.history-card:hover {
  background: #f8f8f8;
}

.empty {
  color: #999;
  margin-top: 20px;
}
</style>
