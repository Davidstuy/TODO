/* =====================================================================
 * ui.js —— 通用 UI 工具
 * =====================================================================
 * 职责：与业务无关的展示层小工具：
 *   - showToast：右下角轻提示（成功 / 失败）
 *   - openModal / closeModal：编辑弹窗开关
 *   - escapeHtml：防止用户输入被当作 HTML 注入（XSS 的第一道防线）
 *   - formatDate：把后端 UTC 时间转成本地可读中文
 * ===================================================================== */

"use strict";

const Ui = {
  /* 轻提示：msg 内容；type 为 "error" 时变红 */
  showToast(msg, type = "info", duration = 2600) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.toggle("is-error", type === "error");
    el.classList.add("is-show");

    /* 每次调用前清掉上一次的定时器，避免连续提示被提前隐藏 */
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => el.classList.remove("is-show"), duration);
  },

  openModal() {
    document.getElementById("edit-modal").hidden = false;
    document.body.style.overflow = "hidden";          /* 锁住背景滚动 */
    const input = document.querySelector("#edit-form [name='title']");
    setTimeout(() => input.focus(), 80);
  },

  closeModal() {
    document.getElementById("edit-modal").hidden = true;
    document.body.style.overflow = "";
  },

  /* XSS 防护：把 < > & " 等字符转成安全实体 */
  escapeHtml(text) {
    if (text == null) return "";
    return String(text)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  },

  /* 后端 created_at 是无时区的 UTC 时间，
     这里在末尾拼 "Z" 告诉 JS 这是 UTC，再转本地时间格式化 */
  formatDate(isoString) {
    const date = new Date(isoString.endsWith("Z") ? isoString : `${isoString}Z`);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    const hh = String(date.getHours()).padStart(2, "0");
    const mm = String(date.getMinutes()).padStart(2, "0");
    return isToday ? `今天 ${hh}:${mm}` : `${date.getMonth() + 1}月${date.getDate()}日 ${hh}:${mm}`;
  },

  /* 取用户名首字符作头像（中文取第一个汉字，英文取首字母大写） */
  initialOf(name) {
    if (!name) return "·";
    const trimmed = name.trim();
    return trimmed[0].toUpperCase();
  },
};
