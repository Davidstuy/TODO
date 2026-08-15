/* =====================================================================
 * auth.js —— 登录 / 注册
 * =====================================================================
 * 职责：
 *   - 登录 / 注册表单的提交与校验
 *   - 成功后保存 token、拉取当前用户、切换进入主视图
 *
 * 教学要点：
 *   1. form 默认 submit 会刷新页面，这里用 preventDefault() 拦下，
 *      改由 fetch 异步提交——这是所有 SPA 表单的标准做法。
 *   2. 登录成功只拿到 token，用户资料还要再调一次 /users/me 获取，
 *      这样「凭证（token）」与「身份资料（用户信息）」分离。
 * ===================================================================== */

"use strict";

const Auth = {
  /* 切换 登录/注册 标签页 */
  switchTab(tabName) {
    const isLogin = tabName === "login";

    /* 高亮对应标签 */
    document.querySelectorAll(".auth-tab").forEach((tab) => {
      const active = tab.dataset.tab === tabName;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active);
    });

    /* 显示对应表单 */
    document.getElementById("login-form").hidden = !isLogin;
    document.getElementById("register-form").hidden = isLogin;
  },

  /* 绑定表单提交事件（由 app.js 调用一次） */
  init() {
    /* 标签切换 */
    document.querySelectorAll(".auth-tab").forEach((tab) => {
      tab.addEventListener("click", () => this.switchTab(tab.dataset.tab));
    });

    /* 登录 */
    document.getElementById("login-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(e.target);
      const submitBtn = e.target.querySelector("button[type='submit']");
      submitBtn.disabled = true;
      submitBtn.textContent = "进入中…";
      try {
        const token = await Api.login(data.get("username"), data.get("password"));
        Api.saveAuth(token.access_token, null);
        await App.enterApp();   // 进入主视图（内部会拉取用户与待办）
      } catch (err) {
        Ui.showToast(err.message, "error");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "进入拾遗";
      }
    });

    /* 注册 */
    document.getElementById("register-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(e.target);
      const submitBtn = e.target.querySelector("button[type='submit']");
      submitBtn.disabled = true;
      submitBtn.textContent = "创建中…";
      try {
        /* 注册成功后返回用户信息，但还没有 token，仍需再登录一次 */
        await Api.register({
          username: data.get("username"),
          email: data.get("email"),
          password: data.get("password"),
        });
        Ui.showToast("注册成功，欢迎加入拾遗");

        const token = await Api.login(data.get("username"), data.get("password"));
        Api.saveAuth(token.access_token, null);
        await App.enterApp();
      } catch (err) {
        Ui.showToast(err.message, "error");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "创建账号";
      }
    });
  },
};
