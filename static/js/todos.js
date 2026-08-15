/* =====================================================================
 * todos.js —— 待办列表业务逻辑
 * =====================================================================
 * 职责：
 *   - 把 State.todos 渲染成页面上的条目（render）
 *   - 新增 / 完成切换 / 编辑 / 删除（改完后刷新列表）
 *   - 过滤切换与计数
 *
 * 教学要点：
 *   1. 「事件委托」：列表本身只绑一个 click 监听，靠 e.target
 *      判断点的是哪个按钮，比给每个按钮绑监听省内存、也简单。
 *   2. 删除用了「二次确认」交互：第一次点变红再点才真正删除，
 *      避免误删——这是企业应用里常见的防呆设计。
 * ===================================================================== */

"use strict";

const Todos = {
  /* 由 app.js 在初始化时调用一次：绑定所有全局事件 */
  init() {
    /* 新增待办 */
    document.getElementById("composer").addEventListener("submit", (e) => this.onCreate(e));

    /* 过滤标签 */
    document.querySelectorAll(".filter-tab").forEach((tab) => {
      tab.addEventListener("click", () => this.setFilter(tab.dataset.filter));
    });

    /* 事件委托：列表里的「勾选 / 编辑 / 删除」统一在这处理 */
    document.getElementById("todo-list").addEventListener("click", (e) => this.onListClick(e));

    /* 弹窗关闭 */
    const modal = document.getElementById("edit-modal");
    modal.addEventListener("click", (e) => {
      if (e.target.dataset.close !== undefined) Ui.closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !modal.hidden) Ui.closeModal();
    });

    /* 编辑表单提交 */
    document.getElementById("edit-form").addEventListener("submit", (e) => this.onEditSubmit(e));
  },

  /* ---------- 渲染 ---------- */

  render() {
    const listEl = document.getElementById("todo-list");
    const emptyEl = document.getElementById("empty-state");
    const items = State.visibleTodos;

    /* 用 createElement 拼接而不是 innerHTML 拼大字符串：
       一方面输入内容经过 escapeHtml 防注入，另一方面动画更可控 */
    listEl.replaceChildren(
      ...items.map((todo, index) => this.renderItem(todo, index))
    );

    /* 空状态：不同过滤条件下的文案不同 */
    emptyEl.hidden = items.length > 0;
    if (items.length === 0) {
      const texts = {
        all: ["此刻，空空如也", "上面写下一件小事，从这里开始。"],
        active: ["没有未完成的事", "所有待办都已了却，松一口气吧。"],
        done: ["还没有完成的事", "完成一件，它就会出现在这里。"],
      };
      const [title, sub] = texts[State.filter];
      document.getElementById("empty-title").textContent = title;
      document.getElementById("empty-sub").textContent = sub;
    }

    this.renderCounts();
    this.renderProgress();
  },

  /* 单条待办 → DOM 节点。index 用于动画错峰（逐条浮现） */
  renderItem(todo, index) {
    const li = document.createElement("li");
    li.className = `todo-item${todo.completed ? " is-done" : ""}`;
    li.dataset.id = todo.id;
    li.style.animationDelay = `${Math.min(index * 45, 360)}ms`;

    /* 勾选框：内嵌 SVG 对勾，完成时由 CSS 画描边动画 */
    const check = document.createElement("button");
    check.type = "button";
    check.className = "todo-check";
    check.title = todo.completed ? "标记为未完成" : "标记为已完成";
    check.innerHTML =
      '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 8.5 L6.2 12 L13.5 4"/></svg>';

    /* 内容区 */
    const body = document.createElement("div");
    body.className = "todo-body";

    const title = document.createElement("p");
    title.className = "todo-title";
    title.textContent = todo.title;

    const meta = document.createElement("p");
    meta.className = "todo-meta";
    meta.textContent = `记于 ${Ui.formatDate(todo.created_at)}`;

    body.append(title);
    if (todo.description) {
      const desc = document.createElement("p");
      desc.className = "todo-desc";
      desc.textContent = todo.description;
      body.append(desc);
    }
    body.append(meta);

    /* 操作区 */
    const actions = document.createElement("div");
    actions.className = "todo-actions";

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "icon-btn";
    editBtn.dataset.action = "edit";
    editBtn.textContent = "改";

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "icon-btn icon-btn--danger";
    delBtn.dataset.action = "delete";
    delBtn.textContent = "删";

    actions.append(editBtn, delBtn);
    li.append(check, body, actions);
    return li;
  },

  /* 刷新工具条徽标数字 */
  renderCounts() {
    const counts = State.counts;
    document.querySelectorAll(".filter-tab").forEach((tab) => {
      const em = tab.querySelector("em");
      if (em) em.textContent = counts[tab.dataset.filter] ?? 0;
    });
  },

  /* 顶部进度行：如「已完成 3 / 5」 */
  renderProgress() {
    const el = document.getElementById("progress-line");
    const { done, all } = State.counts;
    if (all === 0) {
      el.textContent = "今天还没有安排，写下第一件小事吧。";
    } else if (done === all) {
      el.textContent = `今日全部完成 · 共 ${all} 件，做得漂亮。`;
    } else {
      el.textContent = `已完成 ${done} / ${all} 件，还差 ${all - done} 件。`;
    }
  },

  /* ---------- 动作 ---------- */

  async refresh() {
    /* 重拉全部待办（保持后端默认排序） */
    const list = await Api.listTodos();
    State.setTodos(list);
    this.render();
  },

  /* 新增 */
  async onCreate(e) {
    e.preventDefault();
    const input = document.getElementById("composer-input");
    const title = input.value.trim();
    if (!title) return;

    try {
      await Api.createTodo({ title });
      input.value = "";                 // 清空输入框
      Ui.showToast("已记下");
      await this.refresh();
    } catch (err) {
      Ui.showToast(err.message, "error");
    }
  },

  /* 切换过滤条件 */
  setFilter(filter) {
    State.filter = filter;
    document.querySelectorAll(".filter-tab").forEach((tab) => {
      const active = tab.dataset.filter === filter;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active);
    });
    this.render();
  },

  /* 事件委托的处理器：根据点到的元素分发 */
  onListClick(e) {
    const li = e.target.closest(".todo-item");
    if (!li) return;
    const id = Number(li.dataset.id);

    /* 点勾选框：切换完成状态 */
    if (e.target.closest(".todo-check")) {
      return this.toggleComplete(id, li);
    }

    /* 点编辑 */
    if (e.target.closest("[data-action='edit']")) {
      return this.openEdit(id);
    }

    /* 点删除（含二次确认逻辑） */
    if (e.target.closest("[data-action='delete']")) {
      return this.handleDelete(id, e.target.closest("[data-action='delete']"));
    }
  },

  /* 完成 / 取消完成 */
  async toggleComplete(id, li) {
    const todo = State.getTodo(id);
    if (!todo) return;
    try {
      await Api.updateTodo(id, { completed: !todo.completed });
      await this.refresh();
    } catch (err) {
      Ui.showToast(err.message, "error");
    }
  },

  /* 打开编辑弹窗并回填 */
  openEdit(id) {
    const todo = State.getTodo(id);
    if (!todo) return;
    State.editingId = id;
    const form = document.getElementById("edit-form");
    form.elements.title.value = todo.title;
    form.elements.description.value = todo.description || "";
    Ui.openModal();
  },

  /* 保存编辑 */
  async onEditSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const title = form.elements.title.value.trim();
    if (!title) return;

    try {
      await Api.updateTodo(State.editingId, {
        title,
        description: form.elements.description.value.trim() || null,
      });
      Ui.closeModal();
      Ui.showToast("已保存");
      await this.refresh();
    } catch (err) {
      Ui.showToast(err.message, "error");
    }
  },

  /* 删除：第一次点进入确认态（变红 3 秒），再点才真正删除 */
  async handleDelete(id, btn) {
    if (State.deletingId === id) {
      /* 第二次点击：确认删除 */
      try {
        await Api.deleteTodo(id);
        State.deletingId = null;
        Ui.showToast("已删除");

        /* 先做淡出动画，动画结束再刷新列表，过渡更自然 */
        const li = btn.closest(".todo-item");
        li.classList.add("is-removing");
        setTimeout(() => this.refresh(), 380);
      } catch (err) {
        Ui.showToast(err.message, "error");
        State.deletingId = null;
      }
      return;
    }

    /* 第一次点击：进入确认态 */
    State.deletingId = id;
    btn.classList.add("is-confirm");
    btn.textContent = "确认？";

    /* 3 秒内没有再次点击，自动恢复 */
    clearTimeout(this._confirmTimer);
    this._confirmTimer = setTimeout(() => {
      if (State.deletingId === id) {
        State.deletingId = null;
        btn.classList.remove("is-confirm");
        btn.textContent = "删";
      }
    }, 3000);
  },
};
