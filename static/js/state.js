/* =====================================================================
 * state.js —— 应用状态
 * =====================================================================
 * 职责：集中维护一份「前端内存中的状态」，所有模块共享读写。
 *
 * 为什么需要它？
 *   待办列表要支持「按状态过滤 + 计数」，如果每个函数各自 fetch，
 *   数据源就多了，容易不一致。这里统一：
 *     1. todos      —— 从后端拉来的全部待办
 *     2. filter     —— 当前过滤条件（all / active / done）
 *     3. onLogout   —— 全局登出回调（401 时由网络层触发）
 *
 * 真正的持久化（数据库）在后端；这里只是「当前页面的快照」。
 * ===================================================================== */

"use strict";

const State = {
  todos: [],            // 全部待办（来自后端）
  filter: "all",        // 当前过滤条件
  editingId: null,      // 正在编辑的待办 id（弹窗用）
  deletingId: null,     // 正处于「确认删除」状态的行 id
  onLogout: null,       // 全局登出回调，由 app.js 注入

  /* 根据 filter 取当前视图该显示的待办 */
  get visibleTodos() {
    if (this.filter === "active") return this.todos.filter((t) => !t.completed);
    if (this.filter === "done") return this.todos.filter((t) => t.completed);
    return this.todos;
  },

  /* 各类数量，供工具条徽标显示 */
  get counts() {
    return {
      all: this.todos.length,
      active: this.todos.filter((t) => !t.completed).length,
      done: this.todos.filter((t) => t.completed).length,
    };
  },

  /* 刷新状态：整批替换（排序由后端负责，这里保持返回顺序） */
  setTodos(list) {
    this.todos = Array.isArray(list) ? list : [];
  },

  /* 单一待办的查询，供编辑弹窗回填 */
  getTodo(id) {
    return this.todos.find((t) => t.id === id) || null;
  },
};
