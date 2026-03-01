import { defineStore } from "pinia";

export const useUserStore = defineStore("user", {
  state: () => ({
    userId: 1, // 默认用1号用户演示
  }),
  actions: {
    setUserId(id) {
      this.userId = Number(id);
    },
  },
});
