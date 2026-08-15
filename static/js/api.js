/* =====================================================================
 * api.js —— 网络层
 * =====================================================================
 * 职责：所有与后端交互的 fetch 请求都收敛在这里，页面逻辑不碰
 *       fetch，只调用语义化的方法（如 login / listTodos）。
 *
 * 关键知识点：
 *  1. token 统一管理：登录后存 localStorage，每次请求自动带
 *     `Authorization: Bearer <token>` 头。
 *  2. 统一错误处理：任何响应非 2xx 都抛出自定义 ApiError，
 *     并顺手判断 401（token 过期）→ 通知全局登出。
 *  3. 前端永远只拼 HTTP 约定，业务规则（密码哈希、行级隔离）
 *     都在后端，这就是「前后端分离」的边界。
 * ===================================================================== */

"use strict";

/* localStorage 的 key 常量，避免散落在各处写死字符串 */
const TOKEN_KEY = "shiyi_token";
const USER_KEY = "shiyi_user";

const Api = {
  /* 读取当前 token（登录态的依据） */
  get token() {
    return localStorage.getItem(TOKEN_KEY);
  },

  /* 保存登录态：token + 当前用户信息（缓存到 localStorage 便于刷新页面恢复） */
  saveAuth(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  /* 清除登录态 */
  clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  /* 读取缓存的用户信息（可能为空对象） */
  getCachedUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch {
      return null;
    }
  },

  /* ------------------------------------------------------------------
   * request：所有请求的必经之路（薄封装）
   *  - 自动附带 JSON Content-Type 与 Bearer token
   *  - 非 2xx → 抛 ApiError（携带 HTTP 状态码与后端 detail 信息）
   *  - 204 无内容时返回 null
   * ------------------------------------------------------------------ */
  async request(path, { method = "GET", body, isForm = false } = {}) {
    const headers = {};
    if (!isForm) headers["Content-Type"] = "application/json";
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;

    let payload;
    if (body != null) payload = isForm ? body : JSON.stringify(body);

    let resp;
    try {
      resp = await fetch(path, { method, headers, body: payload });
    } catch {
      /* fetch 网络级失败（后端没起、断网等） */
      throw new ApiError(0, "网络连接失败，请确认后端服务已启动");
    }

    if (resp.status === 204) return null;

    /* 先尝试解析 JSON；解析失败（如返回 HTML）也给出友好提示 */
    let data = null;
    try {
      data = await resp.json();
    } catch {
      throw new ApiError(resp.status, "服务返回了无法识别的数据");
    }

    if (!resp.ok) {
      /* 422 时 FastAPI 的 detail 是数组，统一提取第一条信息 */
      const detail = Array.isArray(data?.detail) ? data.detail[0]?.msg : data?.detail;
      throw new ApiError(resp.status, detail || `请求失败（${resp.status}）`);
    }
    return data;
  },

  /* ---------------- 公开接口 ---------------- */

  async register({ username, email, password }) {
    return this.request("/register", { method: "POST", body: { username, email, password } });
  },

  /* 注意：登录接口后端用的是 OAuth2PasswordRequestForm，
     所以必须发 application/x-www-form-urlencoded 而不是 JSON */
  async login(username, password) {
    const body = new URLSearchParams({ username, password });
    return this.request("/login", { method: "POST", body, isForm: true });
  },

  /* ---------------- 需要登录的接口 ---------------- */

  async getMe() {
    return this.request("/users/me");
  },

  async listTodos(params = {}) {
    /* URLSearchParams 自动跳过空值，生成类似 /todos?completed=true */
    const qs = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") qs.append(key, value);
    }
    const query = qs.toString();
    return this.request(`/todos${query ? `?${query}` : ""}`);
  },

  async createTodo({ title, description }) {
    return this.request("/todos", {
      method: "POST",
      body: { title, description: description || null },
    });
  },

  async updateTodo(id, patch) {
    /* PATCH：只传需要改的字段，后端只更新传入部分 */
    return this.request(`/todos/${id}`, { method: "PATCH", body: patch });
  },

  async deleteTodo(id) {
    return this.request(`/todos/${id}`, { method: "DELETE" });
  },
};

/* 自定义错误类型：携带 statusCode，便于上层区分「401 登出」等场景 */
class ApiError extends Error {
  constructor(statusCode, message) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
  }
}
