/* =====================================================================
 * app.js —— 应用入口 / 视图切换
 * =====================================================================
 * 职责：
 *   - 页面加载时决定进入「登录视图」还是「主视图」
 *   - 提供 enterApp / logout 两个全局动作
 *   - 在关键节点调用各模块的 init()，把它们串起来
 *
 * 脚本加载顺序（index.html 底部）：
 *   api.js → ui.js → state.js → auth.js → todos.js → app.js
 * 依赖方向是从下往上的：app.js 最后加载，此时其他模块都就绪了。
 * ===================================================================== */

"use strict";

const App = {
  /* 模块全部初始化（DOM 就绪后调用一次） */
  init() {
    Auth.init();
    Todos.init();

    /* 401 全局处理：token 失效或被盗用时强制回到登录页 */
    State.onLogout = () => this.logout("登录状态已过期，请重新登录");

    /* 顶栏登出按钮 */
    document.getElementById("btn-logout").addEventListener("click", () => this.logout());

    /* 启动路由：有 token 尝试进入主视图，否则停在登录页 */
    if (Api.token) {
      this.enterApp().catch(() => this.showView("auth"));
    } else {
      this.showView("auth");   // 关键：首次访问无 token 时必须显式显示登录页
    }
  },

  /* 进入主视图：拉用户资料 + 待办列表 */
  async enterApp() {
    try {
      const user = await Api.getMe();
      Api.saveAuth(Api.token, user);   // 把用户资料缓存下来
      this.renderUser(user);
      this.renderGreeting(user);
      await Todos.refresh();
      this.showView("app");
    } catch (err) {
      /* token 无效（如服务器重启后密钥变化）→ 清除并回登录页 */
      if (err instanceof ApiError && err.statusCode === 401) {
        this.logout("登录状态已失效，请重新登录");
      } else {
        throw err;
      }
    }
  },

  /* 登出：清 token、回登录页 */
  logout(message) {
    Api.clearAuth();
    Auth.switchTab("login");   // 重置回登录标签，避免停留在注册页
    this.showView("auth");
    if (message) Ui.showToast(message);
  },

  /* 视图切换：只显示一个 #view-* 区域 */
  showView(name) {
    document.getElementById("view-auth").hidden = name !== "auth";
    document.getElementById("view-app").hidden = name !== "app";
    window.scrollTo(0, 0);
  },

  /* 顶栏用户信息 */
  renderUser(user) {
    document.getElementById("user-name").textContent = user.username;
    document.getElementById("user-avatar").textContent = Ui.initialOf(user.username);
  },

  /* 问候语 + 今日日期（随每天变化） */
  renderGreeting(user) {
    const now = new Date();
    const hour = now.getHours();
    const period = hour < 6 ? "夜深了" : hour < 12 ? "早上好" : hour < 18 ? "下午好" : "晚上好";
    document.getElementById("greeting").textContent = `${period}，${user.username}`;

    const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
    document.getElementById("today-label").textContent =
      `${now.getMonth() + 1} 月 ${now.getDate()} 日 · 星期${weekdays[now.getDay()]}`;
  },
};

/* DOM 解析完成后启动（脚本在 body 尾部，DOM 已就绪，直接执行亦可） */
document.addEventListener("DOMContentLoaded", () => App.init());
