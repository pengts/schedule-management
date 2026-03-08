import './style.css';

// Wails Go bindings will be generated at build time
let GoApp = {};

async function initBindings() {
  try {
    const mod = await import('../wailsjs/go/main/App');
    GoApp = mod;
  } catch (e) {
    console.warn('Wails bindings not available, running in browser mode');
  }
}

// ─── 状态 ───
const state = {
  view: 'month',
  year: new Date().getFullYear(),
  month: new Date().getMonth() + 1,
  weekMonday: null, // Date object
};

const COLORS = ['#4A7FE5', '#3dba7a', '#e54d4d', '#f0923e', '#8b5cf6', '#06b6d4'];
const MONTH_NAMES = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
const DAY_LABELS = ['周一','周二','周三','周四','周五','周六','周日'];
const START_HOUR = 6;
const END_HOUR = 23;

// ─── DOM ───
const $content = document.getElementById('main-content');
const $overlay = document.getElementById('modal-overlay');
const $modal = document.getElementById('modal');

// ─── 标题栏事件 ───
// Drag is handled via CSS --wails-draggable attribute

document.getElementById('btn-min').addEventListener('click', () => GoApp.WindowMinimise?.());
document.getElementById('btn-max').addEventListener('click', () => GoApp.WindowToggleMaximise?.());
document.getElementById('btn-close').addEventListener('click', () => GoApp.WindowClose?.());

const $pin = document.getElementById('pin-btn');
let pinned = false;

$pin.addEventListener('click', async () => {
  pinned = !pinned;
  await GoApp.SetAlwaysOnTop?.(pinned);
  updatePinDisplay();
});

function updatePinDisplay() {
  $pin.innerHTML = pinned ? '&#9670;' : '&#9671;';
  $pin.classList.toggle('pinned', pinned);
}

// 导航切换
document.querySelectorAll('.nav-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    state.view = btn.dataset.view;
    render();
  });
});

function updateNavHighlight() {
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === state.view);
  });
}

// ─── 日期工具 ───
function getISOWeek(d) {
  const date = new Date(d);
  date.setHours(0,0,0,0);
  date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7));
  const yearStart = new Date(date.getFullYear(), 0, 4);
  return Math.ceil(((date - yearStart) / 86400000 + 1) / 7);
}

function getMonday(d) {
  const date = new Date(d);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0 ? -6 : 1);
  date.setDate(diff);
  date.setHours(0,0,0,0);
  return date;
}

function formatDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,'0');
  const dd = String(d.getDate()).padStart(2,'0');
  return `${y}-${m}-${dd}`;
}

function weeksOfMonth(year, month) {
  const weeks = [];
  const seen = new Set();
  const lastDay = new Date(year, month, 0).getDate();
  for (let day = 1; day <= lastDay; day++) {
    const d = new Date(year, month - 1, day);
    const wn = getISOWeek(d);
    if (!seen.has(wn)) {
      seen.add(wn);
      const mon = getMonday(d);
      const sun = new Date(mon);
      sun.setDate(sun.getDate() + 6);
      weeks.push({ weekNumber: wn, monday: mon, sunday: sun });
    }
  }
  return weeks;
}

function todayStr() { return formatDate(new Date()); }

// ─── 弹窗 ───
function showModal(html) {
  $modal.innerHTML = html;
  $overlay.style.display = 'flex';
}

function hideModal() {
  $overlay.style.display = 'none';
  $modal.innerHTML = '';
}

$overlay.addEventListener('click', (e) => {
  if (e.target === $overlay) hideModal();
});

// ─── 渲染 ───
function render() {
  updateNavHighlight();
  if (state.view === 'month') renderMonth();
  else if (state.view === 'week') renderWeek();
  else if (state.view === 'day') renderDay();
}

// ═══════════════════════
//  月视图
// ═══════════════════════
async function renderMonth() {
  const now = new Date();
  const currentMonth = now.getMonth() + 1;
  const currentYear = now.getFullYear();

  let html = `
    <div class="view-nav">
      <button class="nav-arrow" id="year-prev">&lt;</button>
      <span class="nav-label">${state.year}年</span>
      <button class="nav-arrow" id="year-next">&gt;</button>
    </div>
    <div class="month-grid">
  `;

  // 预加载所有月份目标
  const allGoals = {};
  for (let m = 1; m <= 12; m++) {
    try {
      allGoals[m] = await GoApp.GetMonthGoals?.(state.year, m) || [];
    } catch(e) { allGoals[m] = []; }
  }

  for (let m = 1; m <= 12; m++) {
    const isCurrent = (state.year === currentYear && m === currentMonth);
    const goals = allGoals[m];
    const goalsHtml = goals.length
      ? `<ul class="goal-list">${goals.map(g => `<li class="goal-item">${escHtml(g.goal)}</li>`).join('')}</ul>`
      : `<div class="goal-empty">暂无目标</div>`;

    html += `
      <div class="month-card ${isCurrent ? 'current' : ''}">
        <div class="month-header">
          <span class="month-title" data-month="${m}">${MONTH_NAMES[m-1]}</span>
          <button class="month-edit-btn" data-edit-month="${m}">编辑</button>
        </div>
        ${goalsHtml}
      </div>
    `;
  }
  html += '</div>';
  $content.innerHTML = html;

  // 事件
  document.getElementById('year-prev').addEventListener('click', () => { state.year--; renderMonth(); });
  document.getElementById('year-next').addEventListener('click', () => { state.year++; renderMonth(); });

  $content.querySelectorAll('.month-title').forEach(el => {
    el.addEventListener('click', () => {
      state.month = parseInt(el.dataset.month);
      state.view = 'week';
      render();
    });
  });

  $content.querySelectorAll('.month-edit-btn').forEach(el => {
    el.addEventListener('click', () => editMonthGoals(parseInt(el.dataset.editMonth)));
  });
}

async function editMonthGoals(month) {
  let goals = [];
  try { goals = await GoApp.GetMonthGoals?.(state.year, month) || []; } catch(e) {}
  const text = goals.map(g => g.goal).join('\n');

  showModal(`
    <h3>${state.year}年 ${MONTH_NAMES[month-1]} - 目标编辑</h3>
    <label class="modal-label">每行输入一个目标</label>
    <textarea id="goal-text" placeholder="输入目标...">${escHtml(text)}</textarea>
    <div class="btn-row">
      <button class="btn btn-secondary" id="modal-cancel">取消</button>
      <button class="btn btn-primary" id="modal-save">保存</button>
    </div>
  `);

  document.getElementById('modal-cancel').addEventListener('click', hideModal);
  document.getElementById('modal-save').addEventListener('click', async () => {
    const val = document.getElementById('goal-text').value.trim();
    const newGoals = val ? val.split('\n').map(s => s.trim()).filter(Boolean) : [];
    await GoApp.SetMonthGoals?.(state.year, month, newGoals);
    hideModal();
    renderMonth();
  });

  document.getElementById('goal-text').focus();
}

// ═══════════════════════
//  周视图
// ═══════════════════════
async function renderWeek() {
  const now = new Date();
  const currentWn = getISOWeek(now);
  const currentYear = now.getFullYear();
  const weeks = weeksOfMonth(state.year, state.month);

  let html = `
    <button class="back-btn" id="back-month">&larr; 返回月视图</button>
    <div class="view-nav">
      <button class="nav-arrow" id="month-prev">&lt;</button>
      <span class="nav-label">${state.year}年 ${MONTH_NAMES[state.month-1]}</span>
      <button class="nav-arrow" id="month-next">&gt;</button>
    </div>
  `;

  for (const w of weeks) {
    const isCurrent = (state.year === currentYear && w.weekNumber === currentWn);
    let tasks = [];
    try { tasks = await GoApp.GetWeekTasks?.(state.year, w.weekNumber) || []; } catch(e) {}

    const monStr = `${w.monday.getMonth()+1}/${w.monday.getDate()}`;
    const sunStr = `${w.sunday.getMonth()+1}/${w.sunday.getDate()}`;

    let tasksHtml = tasks.map(t => `
      <div class="task-item ${t.done ? 'done' : ''}">
        <input type="checkbox" class="task-checkbox" data-tid="${t.id}" ${t.done ? 'checked' : ''} />
        <span class="task-text">${escHtml(t.content)}</span>
        <button class="task-remove" data-remove="${t.id}">&times;</button>
      </div>
    `).join('');

    html += `
      <div class="week-row ${isCurrent ? 'current' : ''}" data-wn="${w.weekNumber}">
        <div class="week-header">
          <span class="week-label" data-goto-day="${formatDate(w.monday)}">第${w.weekNumber}周</span>
          <span class="week-dates">${monStr} - ${sunStr}</span>
        </div>
        ${tasksHtml}
        <input class="add-task-input" placeholder="添加任务，回车确认..." data-wn="${w.weekNumber}" />
      </div>
    `;
  }

  $content.innerHTML = html;

  // 事件
  document.getElementById('back-month').addEventListener('click', () => { state.view = 'month'; render(); });
  document.getElementById('month-prev').addEventListener('click', () => {
    state.month--;
    if (state.month < 1) { state.month = 12; state.year--; }
    renderWeek();
  });
  document.getElementById('month-next').addEventListener('click', () => {
    state.month++;
    if (state.month > 12) { state.month = 1; state.year++; }
    renderWeek();
  });

  $content.querySelectorAll('.week-label').forEach(el => {
    el.addEventListener('click', () => {
      state.weekMonday = new Date(el.dataset.gotoDay);
      state.view = 'day';
      render();
    });
  });

  $content.querySelectorAll('.task-checkbox').forEach(el => {
    el.addEventListener('change', async () => {
      await GoApp.ToggleWeekTask?.(el.dataset.tid);
      renderWeek();
    });
  });

  $content.querySelectorAll('.task-remove').forEach(el => {
    el.addEventListener('click', async () => {
      await GoApp.RemoveWeekTask?.(el.dataset.remove);
      renderWeek();
    });
  });

  $content.querySelectorAll('.add-task-input').forEach(el => {
    el.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter') {
        const text = el.value.trim();
        if (!text) return;
        await GoApp.AddWeekTask?.(state.year, parseInt(el.dataset.wn), text);
        renderWeek();
      }
    });
  });
}

// ═══════════════════════
//  日视图
// ═══════════════════════
async function renderDay() {
  const now = new Date();
  if (!state.weekMonday) {
    state.weekMonday = getMonday(now);
  }
  const mon = state.weekMonday;
  const sun = new Date(mon);
  sun.setDate(sun.getDate() + 6);
  const today = todayStr();

  const hours = [];
  for (let h = START_HOUR; h <= END_HOUR; h++) hours.push(h);

  // 预加载7天的blocks
  const weekDates = [];
  const allBlocks = {};
  for (let i = 0; i < 7; i++) {
    const d = new Date(mon);
    d.setDate(d.getDate() + i);
    weekDates.push(d);
    const ds = formatDate(d);
    try { allBlocks[ds] = await GoApp.GetDayBlocks?.(ds) || []; } catch(e) { allBlocks[ds] = []; }
  }

  let html = `
    <button class="back-btn" id="back-week">&larr; 返回周视图</button>
    <div class="view-nav">
      <button class="nav-arrow" id="week-prev">&lt;</button>
      <span class="nav-label">${mon.getMonth()+1}/${mon.getDate()} - ${sun.getMonth()+1}/${sun.getDate()}</span>
      <button class="nav-arrow" id="week-next">&gt;</button>
    </div>
    <div class="day-grid-wrapper">
      <div class="day-grid">
  `;

  // 表头
  html += `<div class="day-col-header"></div>`;
  for (let i = 0; i < 7; i++) {
    const d = weekDates[i];
    const ds = formatDate(d);
    const isToday = ds === today;
    html += `<div class="day-col-header ${isToday ? 'today' : ''}">
      ${DAY_LABELS[i]}<span class="day-date">${d.getMonth()+1}/${d.getDate()}</span>
    </div>`;
  }

  // 时间行
  for (const hour of hours) {
    html += `<div class="time-label">${hour}:00</div>`;
    for (let i = 0; i < 7; i++) {
      const ds = formatDate(weekDates[i]);
      html += `<div class="time-cell" data-date="${ds}" data-hour="${hour}"></div>`;
    }
  }

  html += '</div></div>';
  $content.innerHTML = html;

  // 在cell上绘制时间块
  const cells = $content.querySelectorAll('.time-cell');
  // 建立索引: cells按行排列 (hour-row, col 0-6)
  // 对每天的blocks，在对应列的第一个cell上place
  for (let i = 0; i < 7; i++) {
    const ds = formatDate(weekDates[i]);
    const blocks = allBlocks[ds] || [];
    for (const blk of blocks) {
      const offsetMin = (blk.startHour - START_HOUR) * 60 + blk.startMinute;
      const topPx = (offsetMin / 60) * 52; // 52px per hour row
      const heightPx = Math.max((blk.duration / 60) * 52, 20);

      // 找到这一列第一个hour的cell
      const cellIdx = 0 * 7 + i; // 第0行第i列
      const cell = cells[cellIdx];
      if (cell) {
        const block = document.createElement('div');
        block.className = 'time-block';
        block.style.cssText = `top:${topPx}px; height:${heightPx}px; background:${blk.color};`;
        block.textContent = blk.title;
        block.addEventListener('click', (e) => {
          e.stopPropagation();
          editBlockDialog(blk);
        });
        cell.appendChild(block);
      }
    }
  }

  // 事件
  document.getElementById('back-week').addEventListener('click', () => { state.view = 'week'; render(); });
  document.getElementById('week-prev').addEventListener('click', () => {
    state.weekMonday = new Date(state.weekMonday);
    state.weekMonday.setDate(state.weekMonday.getDate() - 7);
    renderDay();
  });
  document.getElementById('week-next').addEventListener('click', () => {
    state.weekMonday = new Date(state.weekMonday);
    state.weekMonday.setDate(state.weekMonday.getDate() + 7);
    renderDay();
  });

  cells.forEach(cell => {
    cell.addEventListener('click', () => {
      newBlockDialog(cell.dataset.date, parseInt(cell.dataset.hour));
    });
  });
}

function newBlockDialog(date, hour) {
  blockDialog(date, hour, null);
}

function editBlockDialog(block) {
  blockDialog(block.date, block.startHour, block);
}

function blockDialog(date, hour, block) {
  const isEdit = !!block;
  const title = block ? block.title : '';
  const sHour = block ? block.startHour : hour;
  const sMin = block ? block.startMinute : 0;
  const dur = block ? block.duration : 60;
  const color = block ? block.color : COLORS[0];

  let hourOptions = '';
  for (let h = START_HOUR; h <= END_HOUR; h++) {
    hourOptions += `<option value="${h}" ${h===sHour?'selected':''}>${h}时</option>`;
  }

  let colorDots = COLORS.map(c =>
    `<div class="color-dot ${c===color?'selected':''}" data-color="${c}" style="background:${c}"></div>`
  ).join('');

  showModal(`
    <h3>${isEdit ? '编辑' : '新建'}时间块</h3>
    <label class="modal-label">标题</label>
    <input id="blk-title" value="${escHtml(title)}" placeholder="事项名称" />
    <label class="modal-label">开始时间</label>
    <div class="time-select-row">
      <select id="blk-hour">${hourOptions}</select>
      <select id="blk-min">
        <option value="0" ${sMin===0?'selected':''}>00分</option>
        <option value="30" ${sMin===30?'selected':''}>30分</option>
      </select>
    </div>
    <label class="modal-label">时长 (分钟)</label>
    <input id="blk-dur" type="number" value="${dur}" min="15" step="15" />
    <label class="modal-label">颜色</label>
    <div class="color-options" id="color-options">${colorDots}</div>
    <div class="btn-row">
      ${isEdit ? '<button class="btn btn-danger" id="blk-delete">删除</button>' : ''}
      <div style="flex:1"></div>
      <button class="btn btn-secondary" id="blk-cancel">取消</button>
      <button class="btn btn-primary" id="blk-save">保存</button>
    </div>
  `);

  let selectedColor = color;

  document.querySelectorAll('#color-options .color-dot').forEach(dot => {
    dot.addEventListener('click', () => {
      document.querySelectorAll('#color-options .color-dot').forEach(d => d.classList.remove('selected'));
      dot.classList.add('selected');
      selectedColor = dot.dataset.color;
    });
  });

  document.getElementById('blk-cancel').addEventListener('click', hideModal);
  document.getElementById('blk-title').focus();

  document.getElementById('blk-save').addEventListener('click', async () => {
    const t = document.getElementById('blk-title').value.trim();
    if (!t) return;
    const h = parseInt(document.getElementById('blk-hour').value);
    const m = parseInt(document.getElementById('blk-min').value);
    const d = parseInt(document.getElementById('blk-dur').value);
    if (isEdit) {
      await GoApp.UpdateDayBlock?.(block.id, t, selectedColor, h, m, d);
    } else {
      await GoApp.AddDayBlock?.(date, h, m, d, t, selectedColor);
    }
    hideModal();
    renderDay();
  });

  if (isEdit) {
    document.getElementById('blk-delete').addEventListener('click', async () => {
      await GoApp.RemoveDayBlock?.(block.id);
      hideModal();
      renderDay();
    });
  }
}

// ─── 工具 ───
function escHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// ─── 启动 ───
initBindings().then(() => {
  // 初始化置顶状态
  (async () => {
    try {
      pinned = await GoApp.GetAlwaysOnTop?.() || false;
      updatePinDisplay();
    } catch(e) {}
  })();
  render();
});
