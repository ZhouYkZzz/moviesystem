import { defineStore } from "pinia";

const STORAGE_KEY = "movie-system-user-id";

export const useUserStore = defineStore("user", {
  state: () => ({
    userId: Number(localStorage.getItem(STORAGE_KEY)) || null,
  }),
  getters: {
    isLoggedIn: (state) => Number.isInteger(state.userId) && state.userId > 0,
  },
  actions: {
    setUserId(id) {
      const normalized = Number(id);
      if (!Number.isInteger(normalized) || normalized <= 0) {
        this.userId = null;
        localStorage.removeItem(STORAGE_KEY);
        return;
      }
      this.userId = normalized;
      localStorage.setItem(STORAGE_KEY, String(normalized));
    },
    logout() {
      this.userId = null;
      localStorage.removeItem(STORAGE_KEY);
    },
  },
});
