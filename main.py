"""
极简日程管理 - Python + tkinter + sqlite3
月/周/日 三级计划视图，支持窗口置顶
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import os
import uuid
import datetime
import calendar

# ─── 颜色主题 ───
COLORS = {
    "bg": "#fafafa",
    "surface": "#ffffff",
    "border": "#e0e0e0",
    "text": "#2c2c2c",
    "text2": "#888888",
    "accent": "#4A90D9",
    "accent_light": "#e8f0fe",
    "danger": "#e25555",
    "success": "#52b788",
    "block_colors": ["#4A90D9", "#52b788", "#e25555", "#f4a261", "#9b5de5", "#00bbf9"],
}

FONT = ("Microsoft YaHei", 10)
FONT_S = ("Microsoft YaHei", 9)
FONT_B = ("Microsoft YaHei", 11, "bold")
FONT_TITLE = ("Microsoft YaHei", 14, "bold")


# ─── 数据库 ───
class Database:
    def __init__(self):
        data_dir = os.path.join(os.path.expanduser("~"), ".schedule-mgmt")
        os.makedirs(data_dir, exist_ok=True)
        self.conn = sqlite3.connect(os.path.join(data_dir, "data.db"))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS month_goals (
            id TEXT PRIMARY KEY,
            year INTEGER, month INTEGER,
            goal TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS week_tasks (
            id TEXT PRIMARY KEY,
            year INTEGER, week_number INTEGER,
            content TEXT, done INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS day_blocks (
            id TEXT PRIMARY KEY,
            date TEXT,
            start_hour INTEGER, start_minute INTEGER,
            duration INTEGER, title TEXT, color TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT
        )""")
        self.conn.commit()

    # 月目标
    def get_month_goals(self, year, month):
        rows = self.conn.execute(
            "SELECT id, goal FROM month_goals WHERE year=? AND month=? ORDER BY rowid",
            (year, month),
        ).fetchall()
        return [(r["id"], r["goal"]) for r in rows]

    def set_month_goals(self, year, month, goals: list[str]):
        self.conn.execute(
            "DELETE FROM month_goals WHERE year=? AND month=?", (year, month)
        )
        for g in goals:
            self.conn.execute(
                "INSERT INTO month_goals VALUES (?,?,?,?)",
                (uuid.uuid4().hex[:12], year, month, g),
            )
        self.conn.commit()

    # 周任务
    def get_week_tasks(self, year, week):
        rows = self.conn.execute(
            "SELECT id, content, done FROM week_tasks WHERE year=? AND week_number=? ORDER BY rowid",
            (year, week),
        ).fetchall()
        return [(r["id"], r["content"], bool(r["done"])) for r in rows]

    def add_week_task(self, year, week, content):
        self.conn.execute(
            "INSERT INTO week_tasks VALUES (?,?,?,?,0)",
            (uuid.uuid4().hex[:12], year, week, content),
        )
        self.conn.commit()

    def toggle_week_task(self, task_id):
        self.conn.execute(
            "UPDATE week_tasks SET done = 1 - done WHERE id=?", (task_id,)
        )
        self.conn.commit()

    def remove_week_task(self, task_id):
        self.conn.execute("DELETE FROM week_tasks WHERE id=?", (task_id,))
        self.conn.commit()

    # 日时间块
    def get_day_blocks(self, date_str):
        rows = self.conn.execute(
            "SELECT * FROM day_blocks WHERE date=? ORDER BY start_hour, start_minute",
            (date_str,),
        ).fetchall()
        return [dict(r) for r in rows]

    def add_day_block(self, date_str, start_hour, start_minute, duration, title, color):
        self.conn.execute(
            "INSERT INTO day_blocks VALUES (?,?,?,?,?,?,?)",
            (uuid.uuid4().hex[:12], date_str, start_hour, start_minute, duration, title, color),
        )
        self.conn.commit()

    def update_day_block(self, block_id, **kwargs):
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [block_id]
        self.conn.execute(f"UPDATE day_blocks SET {sets} WHERE id=?", vals)
        self.conn.commit()

    def remove_day_block(self, block_id):
        self.conn.execute("DELETE FROM day_blocks WHERE id=?", (block_id,))
        self.conn.commit()

    # 设置
    def get_setting(self, key, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value))
        )
        self.conn.commit()


# ─── 日期工具 ───
def iso_week(date: datetime.date) -> int:
    return date.isocalendar()[1]


def monday_of_week(year, week):
    """根据ISO年/周号返回该周周一"""
    jan4 = datetime.date(year, 1, 4)
    start = jan4 - datetime.timedelta(days=jan4.weekday())
    return start + datetime.timedelta(weeks=week - 1)


def weeks_of_month(year, month):
    """返回该月涉及的所有ISO周 [(week_number, monday_date), ...]"""
    first = datetime.date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = datetime.date(year, month, last_day)

    seen = []
    d = first
    while d <= last:
        wn = iso_week(d)
        mon = d - datetime.timedelta(days=d.weekday())
        if not seen or seen[-1][0] != wn:
            seen.append((wn, mon))
        d += datetime.timedelta(days=1)
    return seen


# ─── 主应用 ───
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.title("日程管理")
        self.geometry("1050x700")
        self.minsize(850, 550)
        self.configure(bg=COLORS["bg"])

        # 置顶状态
        self._pinned = self.db.get_setting("pinned", "0") == "1"
        self.attributes("-topmost", self._pinned)

        # 导航状态
        self.current_view = "month"
        self.view_year = datetime.date.today().year
        self.view_month = datetime.date.today().month
        self.view_week_monday = None  # datetime.date

        self._build_titlebar()
        self._content = tk.Frame(self, bg=COLORS["bg"])
        self._content.pack(fill="both", expand=True)

        self._show_month_view()

    # ─── 标题栏 ───
    def _build_titlebar(self):
        bar = tk.Frame(self, bg=COLORS["surface"], height=40)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        # 视图切换
        nav = tk.Frame(bar, bg=COLORS["surface"])
        nav.pack(side="left", padx=8)

        self._nav_btns = {}
        for label, view in [("月", "month"), ("周", "week"), ("日", "day")]:
            btn = tk.Label(
                nav, text=f"  {label}  ", font=FONT, cursor="hand2",
                bg=COLORS["surface"], fg=COLORS["text2"],
                padx=10, pady=4,
            )
            btn.pack(side="left", padx=2)
            btn.bind("<Button-1>", lambda e, v=view: self._switch_view(v))
            self._nav_btns[view] = btn

        # 窗口控制（右侧）
        ctrl = tk.Frame(bar, bg=COLORS["surface"])
        ctrl.pack(side="right", padx=4)

        close_btn = tk.Label(ctrl, text=" X ", font=FONT_S, cursor="hand2",
                             bg=COLORS["surface"], fg=COLORS["text2"])
        close_btn.pack(side="right", padx=2)
        close_btn.bind("<Button-1>", lambda e: self.destroy())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(bg=COLORS["danger"], fg="white"))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(bg=COLORS["surface"], fg=COLORS["text2"]))

        # 置顶按钮
        self._pin_label = tk.Label(
            ctrl, text="", font=FONT, cursor="hand2",
            bg=COLORS["surface"], padx=6, pady=4,
        )
        self._pin_label.pack(side="right", padx=2)
        self._pin_label.bind("<Button-1>", lambda e: self._toggle_pin())
        self._update_pin_display()
        self._update_nav_highlight()

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self.attributes("-topmost", self._pinned)
        self.db.set_setting("pinned", "1" if self._pinned else "0")
        self._update_pin_display()

    def _update_pin_display(self):
        if self._pinned:
            self._pin_label.configure(text="\u25c6", fg=COLORS["accent"])
        else:
            self._pin_label.configure(text="\u25c7", fg=COLORS["text2"])

    def _update_nav_highlight(self):
        for view, btn in self._nav_btns.items():
            if view == self.current_view:
                btn.configure(bg=COLORS["accent"], fg="white")
            else:
                btn.configure(bg=COLORS["surface"], fg=COLORS["text2"])

    def _switch_view(self, view):
        self.current_view = view
        self._update_nav_highlight()
        if view == "month":
            self._show_month_view()
        elif view == "week":
            self._show_week_view()
        elif view == "day":
            self._show_day_view()

    def _clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()

    # ═══════════════════════════════════════
    #  月视图
    # ═══════════════════════════════════════
    def _show_month_view(self):
        self._clear_content()
        self.current_view = "month"
        self._update_nav_highlight()

        today = datetime.date.today()

        # 年份切换
        nav = tk.Frame(self._content, bg=COLORS["bg"])
        nav.pack(pady=(16, 10))

        tk.Button(nav, text="<", font=FONT, width=3, relief="flat",
                  bg=COLORS["surface"], command=lambda: self._change_year(-1)).pack(side="left", padx=8)
        self._year_label = tk.Label(nav, text=f"{self.view_year}年", font=FONT_TITLE, bg=COLORS["bg"])
        self._year_label.pack(side="left", padx=8)
        tk.Button(nav, text=">", font=FONT, width=3, relief="flat",
                  bg=COLORS["surface"], command=lambda: self._change_year(1)).pack(side="left", padx=8)

        # 网格
        grid = tk.Frame(self._content, bg=COLORS["bg"])
        grid.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        for c in range(4):
            grid.columnconfigure(c, weight=1, uniform="col")
        for r in range(3):
            grid.rowconfigure(r, weight=1, uniform="row")

        for m in range(1, 13):
            r, c = divmod(m - 1, 4)
            is_current = (self.view_year == today.year and m == today.month)
            self._build_month_card(grid, r, c, m, is_current)

    def _build_month_card(self, parent, row, col, month, is_current):
        border_color = COLORS["accent"] if is_current else COLORS["border"]
        bd_width = 2 if is_current else 1

        frame = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=border_color,
                         highlightthickness=bd_width, padx=10, pady=8)
        frame.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        # 头部
        header = tk.Frame(frame, bg=COLORS["surface"])
        header.pack(fill="x")

        title = tk.Label(header, text=f"{month}月", font=FONT_B, bg=COLORS["surface"],
                         fg=COLORS["text"], cursor="hand2")
        title.pack(side="left")
        title.bind("<Button-1>", lambda e, m=month: self._goto_week_from_month(m))
        title.bind("<Enter>", lambda e: title.configure(fg=COLORS["accent"]))
        title.bind("<Leave>", lambda e: title.configure(fg=COLORS["text"]))

        edit_btn = tk.Label(header, text="编辑", font=FONT_S, bg=COLORS["surface"],
                            fg=COLORS["accent"], cursor="hand2")
        edit_btn.pack(side="right")
        edit_btn.bind("<Button-1>", lambda e, m=month: self._edit_month_goals(m))

        # 目标列表
        goals = self.db.get_month_goals(self.view_year, month)
        if goals:
            for _, g in goals:
                lbl = tk.Label(frame, text=g, font=FONT_S, bg=COLORS["surface"],
                               fg=COLORS["text2"], anchor="w", wraplength=200)
                lbl.pack(fill="x", pady=1)
        else:
            tk.Label(frame, text="暂无目标", font=FONT_S, bg=COLORS["surface"],
                     fg=COLORS["border"]).pack(anchor="w", pady=4)

    def _change_year(self, delta):
        self.view_year += delta
        self._show_month_view()

    def _goto_week_from_month(self, month):
        self.view_month = month
        self._switch_view("week")

    def _edit_month_goals(self, month):
        goals = self.db.get_month_goals(self.view_year, month)
        text = "\n".join(g for _, g in goals)

        win = tk.Toplevel(self)
        win.title(f"{self.view_year}年{month}月 - 目标")
        win.geometry("380x280")
        win.configure(bg=COLORS["surface"])
        win.transient(self)
        win.grab_set()

        tk.Label(win, text=f"{self.view_year}年{month}月 - 目标编辑", font=FONT_B,
                 bg=COLORS["surface"]).pack(pady=(12, 6))
        tk.Label(win, text="每行一个目标", font=FONT_S, bg=COLORS["surface"],
                 fg=COLORS["text2"]).pack()

        txt = tk.Text(win, font=FONT, width=40, height=8, relief="solid", bd=1,
                      highlightthickness=1, highlightcolor=COLORS["accent"])
        txt.pack(padx=16, pady=8, fill="both", expand=True)
        txt.insert("1.0", text)

        btn_frame = tk.Frame(win, bg=COLORS["surface"])
        btn_frame.pack(pady=(0, 12))

        def save():
            content = txt.get("1.0", "end").strip()
            new_goals = [line.strip() for line in content.split("\n") if line.strip()]
            self.db.set_month_goals(self.view_year, month, new_goals)
            win.destroy()
            self._show_month_view()

        tk.Button(btn_frame, text="取消", font=FONT_S, relief="flat", bg=COLORS["bg"],
                  width=8, command=win.destroy).pack(side="left", padx=4)
        tk.Button(btn_frame, text="保存", font=FONT_S, relief="flat", bg=COLORS["accent"],
                  fg="white", width=8, command=save).pack(side="left", padx=4)

    # ═══════════════════════════════════════
    #  周视图
    # ═══════════════════════════════════════
    def _show_week_view(self):
        self._clear_content()
        self.current_view = "week"
        self._update_nav_highlight()

        today = datetime.date.today()
        current_wn = iso_week(today)

        # 顶部：返回 + 月份切换
        top = tk.Frame(self._content, bg=COLORS["bg"])
        top.pack(fill="x", padx=20, pady=(12, 0))

        back = tk.Label(top, text="< 返回月视图", font=FONT_S, bg=COLORS["bg"],
                        fg=COLORS["text2"], cursor="hand2")
        back.pack(side="left")
        back.bind("<Button-1>", lambda e: self._switch_view("month"))
        back.bind("<Enter>", lambda e: back.configure(fg=COLORS["accent"]))
        back.bind("<Leave>", lambda e: back.configure(fg=COLORS["text2"]))

        nav = tk.Frame(self._content, bg=COLORS["bg"])
        nav.pack(pady=(8, 12))

        tk.Button(nav, text="<", font=FONT, width=3, relief="flat",
                  bg=COLORS["surface"], command=lambda: self._change_month(-1)).pack(side="left", padx=8)
        tk.Label(nav, text=f"{self.view_year}年 {self.view_month}月",
                 font=FONT_TITLE, bg=COLORS["bg"]).pack(side="left", padx=8)
        tk.Button(nav, text=">", font=FONT, width=3, relief="flat",
                  bg=COLORS["surface"], command=lambda: self._change_month(1)).pack(side="left", padx=8)

        # 可滚动区域
        container = tk.Frame(self._content, bg=COLORS["bg"])
        container.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        canvas = tk.Canvas(container, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLORS["bg"])

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        weeks = weeks_of_month(self.view_year, self.view_month)

        for wn, mon in weeks:
            sun = mon + datetime.timedelta(days=6)
            is_current = (self.view_year == today.year and wn == current_wn)
            self._build_week_row(scroll_frame, wn, mon, sun, is_current)

    def _build_week_row(self, parent, week_number, monday, sunday, is_current):
        border_color = COLORS["accent"] if is_current else COLORS["border"]
        bd = 2 if is_current else 1

        frame = tk.Frame(parent, bg=COLORS["surface"], highlightbackground=border_color,
                         highlightthickness=bd, padx=14, pady=10)
        frame.pack(fill="x", pady=4, padx=60)

        # 头部
        header = tk.Frame(frame, bg=COLORS["surface"])
        header.pack(fill="x")

        title = tk.Label(header, text=f"第{week_number}周", font=FONT_B,
                         bg=COLORS["surface"], cursor="hand2")
        title.pack(side="left")
        title.bind("<Button-1>", lambda e, m=monday: self._goto_day_from_week(m))
        title.bind("<Enter>", lambda e: title.configure(fg=COLORS["accent"]))
        title.bind("<Leave>", lambda e: title.configure(fg=COLORS["text"]))

        tk.Label(header, text=f"{monday.month}/{monday.day} - {sunday.month}/{sunday.day}",
                 font=FONT_S, bg=COLORS["surface"], fg=COLORS["text2"]).pack(side="right")

        # 任务列表
        tasks = self.db.get_week_tasks(self.view_year, week_number)
        for tid, content, done in tasks:
            self._build_task_item(frame, week_number, tid, content, done)

        # 添加任务输入
        entry_frame = tk.Frame(frame, bg=COLORS["surface"])
        entry_frame.pack(fill="x", pady=(6, 0))

        entry = tk.Entry(entry_frame, font=FONT_S, relief="solid", bd=1,
                         highlightthickness=1, highlightcolor=COLORS["accent"])
        entry.pack(fill="x")
        entry.insert(0, "添加任务...")
        entry.configure(fg=COLORS["text2"])

        def on_focus_in(e):
            if entry.get() == "添加任务...":
                entry.delete(0, "end")
                entry.configure(fg=COLORS["text"])

        def on_focus_out(e):
            if not entry.get():
                entry.insert(0, "添加任务...")
                entry.configure(fg=COLORS["text2"])

        def on_enter(e):
            text = entry.get().strip()
            if text and text != "添加任务...":
                self.db.add_week_task(self.view_year, week_number, text)
                self._show_week_view()

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        entry.bind("<Return>", on_enter)

    def _build_task_item(self, parent, week_number, task_id, content, done):
        row = tk.Frame(parent, bg=COLORS["surface"])
        row.pack(fill="x", pady=2)

        var = tk.BooleanVar(value=done)
        cb = tk.Checkbutton(row, variable=var, bg=COLORS["surface"], activebackground=COLORS["surface"],
                            command=lambda: (self.db.toggle_week_task(task_id), self._show_week_view()))
        cb.pack(side="left")

        fg = COLORS["text2"] if done else COLORS["text"]
        lbl = tk.Label(row, text=content, font=FONT_S, bg=COLORS["surface"], fg=fg,
                       anchor="w")
        if done:
            lbl.configure(font=("Microsoft YaHei", 9, "overstrike"))
        lbl.pack(side="left", fill="x", expand=True)

        del_btn = tk.Label(row, text="x", font=FONT_S, bg=COLORS["surface"],
                           fg=COLORS["surface"], cursor="hand2")
        del_btn.pack(side="right", padx=4)

        def show_del(e): del_btn.configure(fg=COLORS["danger"])
        def hide_del(e): del_btn.configure(fg=COLORS["surface"])

        row.bind("<Enter>", show_del)
        row.bind("<Leave>", hide_del)
        del_btn.bind("<Button-1>", lambda e: (self.db.remove_week_task(task_id), self._show_week_view()))

    def _change_month(self, delta):
        self.view_month += delta
        if self.view_month > 12:
            self.view_month = 1
            self.view_year += 1
        elif self.view_month < 1:
            self.view_month = 12
            self.view_year -= 1
        self._show_week_view()

    def _goto_day_from_week(self, monday):
        self.view_week_monday = monday
        self._switch_view("day")

    # ═══════════════════════════════════════
    #  日视图
    # ═══════════════════════════════════════
    def _show_day_view(self):
        self._clear_content()
        self.current_view = "day"
        self._update_nav_highlight()

        today = datetime.date.today()
        if self.view_week_monday is None:
            self.view_week_monday = today - datetime.timedelta(days=today.weekday())

        mon = self.view_week_monday
        sun = mon + datetime.timedelta(days=6)

        # 顶部
        top = tk.Frame(self._content, bg=COLORS["bg"])
        top.pack(fill="x", padx=20, pady=(12, 0))

        back = tk.Label(top, text="< 返回周视图", font=FONT_S, bg=COLORS["bg"],
                        fg=COLORS["text2"], cursor="hand2")
        back.pack(side="left")
        back.bind("<Button-1>", lambda e: self._switch_view("week"))
        back.bind("<Enter>", lambda e: back.configure(fg=COLORS["accent"]))
        back.bind("<Leave>", lambda e: back.configure(fg=COLORS["text2"]))

        nav = tk.Frame(self._content, bg=COLORS["bg"])
        nav.pack(pady=(8, 10))

        tk.Button(nav, text="<", font=FONT, width=3, relief="flat",
                  bg=COLORS["surface"], command=lambda: self._change_week(-1)).pack(side="left", padx=8)
        tk.Label(nav, text=f"{mon.month}/{mon.day} - {sun.month}/{sun.day}",
                 font=FONT_TITLE, bg=COLORS["bg"]).pack(side="left", padx=8)
        tk.Button(nav, text=">", font=FONT, width=3, relief="flat",
                  bg=COLORS["surface"], command=lambda: self._change_week(1)).pack(side="left", padx=8)

        # 时间表容器（可滚动）
        container = tk.Frame(self._content, bg=COLORS["bg"])
        container.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        canvas = tk.Canvas(container, bg=COLORS["surface"], highlightthickness=0)
        v_scroll = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        h_scroll = tk.Scrollbar(container, orient="horizontal", command=canvas.xview)

        inner = tk.Frame(canvas, bg=COLORS["surface"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        START_HOUR = 6
        END_HOUR = 23
        ROW_H = 48
        COL_W = 120
        TIME_W = 50

        day_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        # 表头
        tk.Label(inner, text="", width=7, bg=COLORS["surface"],
                 relief="solid", bd=0).grid(row=0, column=0, sticky="nsew")

        for di in range(7):
            d = mon + datetime.timedelta(days=di)
            is_today = (d == today)
            bg = COLORS["accent_light"] if is_today else COLORS["surface"]
            fg = COLORS["accent"] if is_today else COLORS["text"]
            lbl = tk.Label(inner, text=f"{day_labels[di]}\n{d.month}/{d.day}",
                           font=FONT_S, bg=bg, fg=fg, width=15, height=2,
                           relief="groove", bd=1)
            lbl.grid(row=0, column=di + 1, sticky="nsew")

        # 时间行
        for hi, hour in enumerate(range(START_HOUR, END_HOUR + 1)):
            row_idx = hi + 1

            tk.Label(inner, text=f"{hour}:00", font=("Microsoft YaHei", 8),
                     bg=COLORS["surface"], fg=COLORS["text2"], width=7,
                     relief="groove", bd=1, height=3).grid(row=row_idx, column=0, sticky="nsew")

            for di in range(7):
                d = mon + datetime.timedelta(days=di)
                date_str = d.strftime("%Y-%m-%d")

                cell = tk.Frame(inner, bg=COLORS["surface"], width=COL_W, height=ROW_H,
                                relief="groove", bd=1)
                cell.grid(row=row_idx, column=di + 1, sticky="nsew")
                cell.grid_propagate(False)

                cell.bind("<Button-1>", lambda e, ds=date_str, h=hour: self._new_block_dialog(ds, h))

                # 只在第一行绘制该天所有时间块
                if hour == START_HOUR:
                    blocks = self.db.get_day_blocks(date_str)
                    for blk in blocks:
                        self._draw_block_on_grid(inner, blk, di + 1, START_HOUR, ROW_H)

    def _draw_block_on_grid(self, grid, block, col, start_hour, row_h):
        """在grid上用place方式绘制时间块"""
        offset_minutes = (block["start_hour"] - start_hour) * 60 + block["start_minute"]
        y = int(offset_minutes / 60 * row_h) + row_h  # +row_h 跳过表头行高度
        h = max(int(block["duration"] / 60 * row_h), 18)

        blk_label = tk.Label(
            grid, text=block["title"], font=("Microsoft YaHei", 8),
            bg=block["color"], fg="white", anchor="nw", padx=3, pady=1,
            wraplength=100, cursor="hand2",
        )
        # 使用grid info计算位置比较复杂，改用绝对坐标的方式
        # 我们在cell的第一行已经有了blocks数据，但place需要在canvas内...
        # 简化方案：在对应cell内创建label
        # 找到该cell
        for w in grid.winfo_children():
            info = w.grid_info()
            if not info:
                continue
            gr = int(info.get("row", -1))
            gc = int(info.get("column", -1))
            if gc == col and gr == 1:  # 第一个数据行
                # 计算相对于第一个数据行的偏移
                blk_label = tk.Label(
                    w, text=block["title"], font=("Microsoft YaHei", 8),
                    bg=block["color"], fg="white", anchor="nw", padx=3, pady=1,
                    cursor="hand2",
                )
                rel_y = offset_minutes / 60 * row_h
                blk_label.place(x=1, y=rel_y, width=w.winfo_reqwidth() - 4, height=h)
                blk_label.bind("<Button-1>", lambda e, b=block: self._edit_block_dialog(b))
                break

    def _new_block_dialog(self, date_str, hour):
        self._block_dialog(date_str, hour=hour)

    def _edit_block_dialog(self, block):
        self._block_dialog(block["date"], block=block)

    def _block_dialog(self, date_str, hour=8, block=None):
        win = tk.Toplevel(self)
        win.title("编辑时间块" if block else "新建时间块")
        win.geometry("320x340")
        win.configure(bg=COLORS["surface"])
        win.transient(self)
        win.grab_set()

        pad = {"padx": 16, "pady": 4}

        tk.Label(win, text="标题", font=FONT_S, bg=COLORS["surface"]).pack(anchor="w", **pad)
        title_entry = tk.Entry(win, font=FONT, relief="solid", bd=1)
        title_entry.pack(fill="x", padx=16)

        tk.Label(win, text="开始时间", font=FONT_S, bg=COLORS["surface"]).pack(anchor="w", **pad)
        time_frame = tk.Frame(win, bg=COLORS["surface"])
        time_frame.pack(fill="x", padx=16)

        hour_var = tk.IntVar(value=block["start_hour"] if block else hour)
        min_var = tk.IntVar(value=block["start_minute"] if block else 0)

        hour_spin = tk.Spinbox(time_frame, from_=0, to=23, textvariable=hour_var,
                               width=5, font=FONT)
        hour_spin.pack(side="left")
        tk.Label(time_frame, text="时", font=FONT_S, bg=COLORS["surface"]).pack(side="left", padx=4)
        min_combo = ttk.Combobox(time_frame, values=["0", "30"], textvariable=min_var,
                                 width=4, font=FONT, state="readonly")
        min_combo.pack(side="left")
        tk.Label(time_frame, text="分", font=FONT_S, bg=COLORS["surface"]).pack(side="left", padx=4)

        tk.Label(win, text="时长(分钟)", font=FONT_S, bg=COLORS["surface"]).pack(anchor="w", **pad)
        dur_var = tk.IntVar(value=block["duration"] if block else 60)
        dur_spin = tk.Spinbox(win, from_=15, to=480, increment=15, textvariable=dur_var,
                              font=FONT, relief="solid", bd=1)
        dur_spin.pack(fill="x", padx=16)

        tk.Label(win, text="颜色", font=FONT_S, bg=COLORS["surface"]).pack(anchor="w", **pad)
        color_frame = tk.Frame(win, bg=COLORS["surface"])
        color_frame.pack(padx=16, anchor="w")

        color_var = tk.StringVar(value=block["color"] if block else COLORS["block_colors"][0])

        for c in COLORS["block_colors"]:
            rb = tk.Radiobutton(color_frame, bg=c, selectcolor=c, activebackground=c,
                                variable=color_var, value=c, indicatoron=False,
                                width=3, height=1, relief="raised", bd=2, cursor="hand2")
            rb.pack(side="left", padx=2)

        if block:
            title_entry.insert(0, block["title"])

        # 按钮
        btn_frame = tk.Frame(win, bg=COLORS["surface"])
        btn_frame.pack(fill="x", padx=16, pady=(16, 12))

        if block:
            tk.Button(btn_frame, text="删除", font=FONT_S, fg=COLORS["danger"], relief="flat",
                      command=lambda: (self.db.remove_day_block(block["id"]), win.destroy(), self._show_day_view())
                      ).pack(side="left")

        tk.Button(btn_frame, text="保存", font=FONT_S, bg=COLORS["accent"], fg="white",
                  relief="flat", width=8,
                  command=lambda: self._save_block(win, date_str, block,
                                                   title_entry.get(), hour_var.get(), min_var.get(),
                                                   dur_var.get(), color_var.get())
                  ).pack(side="right", padx=4)
        tk.Button(btn_frame, text="取消", font=FONT_S, relief="flat", bg=COLORS["bg"],
                  width=8, command=win.destroy).pack(side="right")

    def _save_block(self, win, date_str, block, title, hour, minute, duration, color):
        title = title.strip()
        if not title:
            return
        if block:
            self.db.update_day_block(block["id"], title=title, start_hour=hour,
                                     start_minute=minute, duration=duration, color=color)
        else:
            self.db.add_day_block(date_str, hour, minute, duration, title, color)
        win.destroy()
        self._show_day_view()

    def _change_week(self, delta):
        self.view_week_monday += datetime.timedelta(weeks=delta)
        self._show_day_view()


if __name__ == "__main__":
    app = App()
    app.mainloop()
