<template>
  <div class="container">
    <div class="topbar">
      <div class="brand">
        <h1>Movie System · 用户登录</h1>
        <p>支持 userId 登录，新用户可一键注册</p>
      </div>
    </div>

    <div class="section auth-panel" v-if="!showRegister">
      <h2 class="section-title">登录</h2>

      <div class="form-row">
        <label class="muted">用户 ID</label>
        <input class="input" v-model="userIdInput" placeholder="请输入 userId" />
      </div>

      <div class="form-row">
        <label class="muted">密码</label>
        <input class="input" type="password" v-model="passwordInput" placeholder="请输入密码" />
      </div>

      <div class="controls">
        <button class="btn" @click="doLogin">登录</button>
        <button class="btn" @click="openRegister">注册</button>
      </div>

      <p class="muted" v-if="loginMessage">{{ loginMessage }}</p>
    </div>

    <div class="section auth-panel" v-if="showRegister">
      <h2 class="section-title">注册</h2>

      <div class="form-row">
        <label class="muted">注册密码</label>
        <input class="input" type="password" v-model="registerPassword" placeholder="请输入密码" />
      </div>

      <div class="form-row">
        <label class="muted">确认密码</label>
        <input class="input" type="password" v-model="registerPasswordConfirm" placeholder="请再次输入密码" />
      </div>

      <div class="controls">
        <button class="btn" @click="doRegister">注册新用户</button>
        <button class="btn" @click="closeRegister">取消</button>
      </div>

      <p class="muted">userID自动分配</p>
      <p class="muted" v-if="registerMessage">{{ registerMessage }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "../store/user";
import { loginByUserId, registerUser } from "../api/reco";

const router = useRouter();
const userStore = useUserStore();

const userIdInput = ref("");
const passwordInput = ref("");
const loginMessage = ref("");
const registerMessage = ref("");
const registerPassword = ref("");
const registerPasswordConfirm = ref("");
const showRegister = ref(false);

onMounted(() => {
  if (userStore.isLoggedIn) {
    router.replace("/");
  }
});

async function doLogin() {
  const userId = Number(userIdInput.value);
  if (!Number.isInteger(userId) || userId <= 0) {
    loginMessage.value = "请输入正确的 userId（正整数）";
    return;
  }

  try {
    await loginByUserId(userId, passwordInput.value || "");
    userStore.setUserId(userId);
    router.replace("/");
  } catch (e) {
    loginMessage.value = e?.response?.data?.message || "登录失败，请检查 userId 或密码";
  }
}

async function doRegister() {
  registerMessage.value = "";
  if (!registerPassword.value) {
    registerMessage.value = "请输入注册密码";
    return;
  }
  if (registerPassword.value !== registerPasswordConfirm.value) {
    registerMessage.value = "两次输入的密码不一致";
    return;
  }

  try {
    const res = await registerUser(registerPassword.value);
    const userId = Number(res?.data?.userId);
    if (!Number.isInteger(userId) || userId <= 0) {
      registerMessage.value = "注册失败：未获取到有效 userId";
      return;
    }
    userIdInput.value = String(userId);
    passwordInput.value = registerPassword.value;
    showRegister.value = false;
    loginMessage.value = `注册成功，请使用 userId ${userId} 登录`;
    registerMessage.value = "";
    registerPassword.value = "";
    registerPasswordConfirm.value = "";
  } catch (e) {
    registerMessage.value = e?.response?.data?.message || "注册失败，请稍后重试";
  }
}

function openRegister() {
  loginMessage.value = "";
  showRegister.value = true;
}

function closeRegister() {
  showRegister.value = false;
  registerMessage.value = "";
  registerPassword.value = "";
  registerPasswordConfirm.value = "";
}
</script>

<style scoped>
.auth-panel {
  max-width: 420px;
  margin: 20px auto 0;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}
</style>
