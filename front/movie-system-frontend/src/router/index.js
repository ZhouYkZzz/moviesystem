import { createRouter, createWebHistory } from "vue-router";
import Home from "../views/Home.vue";
import Detail from "../views/Detail.vue";
import History from "../views/History.vue";
import Login from "../views/Login.vue";
import { useUserStore } from "../store/user";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: Login },
    { path: "/", component: Home, meta: { requiresAuth: true } },
    { path: "/movie/:id", component: Detail, meta: { requiresAuth: true } },
    { path: "/history", component: History, meta: { requiresAuth: true } }
  ],
});

router.beforeEach((to) => {
  const userStore = useUserStore();
  if (to.path === "/login") {
    if (userStore.isLoggedIn) {
      return "/";
    }
    return true;
  }
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    return "/login";
  }
  return true;
});

export default router;
