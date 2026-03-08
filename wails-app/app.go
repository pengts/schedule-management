package main

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"

	"github.com/google/uuid"
	_ "modernc.org/sqlite"
	wailsRuntime "github.com/wailsapp/wails/v2/pkg/runtime"
)

type App struct {
	ctx context.Context
	db  *sql.DB
}

func NewApp() *App {
	return &App{}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	a.initDB()
}

func (a *App) initDB() {
	homeDir, _ := os.UserHomeDir()
	dataDir := filepath.Join(homeDir, ".schedule-mgmt")
	os.MkdirAll(dataDir, 0755)

	db, err := sql.Open("sqlite", filepath.Join(dataDir, "data.db"))
	if err != nil {
		panic(err)
	}
	a.db = db

	a.db.Exec(`CREATE TABLE IF NOT EXISTS month_goals (
		id TEXT PRIMARY KEY, year INTEGER, month INTEGER, goal TEXT
	)`)
	a.db.Exec(`CREATE TABLE IF NOT EXISTS week_tasks (
		id TEXT PRIMARY KEY, year INTEGER, week_number INTEGER,
		content TEXT, done INTEGER DEFAULT 0
	)`)
	a.db.Exec(`CREATE TABLE IF NOT EXISTS day_blocks (
		id TEXT PRIMARY KEY, date TEXT,
		start_hour INTEGER, start_minute INTEGER,
		duration INTEGER, title TEXT, color TEXT
	)`)
	a.db.Exec(`CREATE TABLE IF NOT EXISTS settings (
		key TEXT PRIMARY KEY, value TEXT
	)`)
}

// ─── 窗口控制 ───

func (a *App) WindowMinimise() {
	wailsRuntime.WindowMinimise(a.ctx)
}

func (a *App) WindowToggleMaximise() {
	wailsRuntime.WindowToggleMaximise(a.ctx)
}

func (a *App) WindowClose() {
	wailsRuntime.Quit(a.ctx)
}

func (a *App) SetAlwaysOnTop(onTop bool) {
	wailsRuntime.WindowSetAlwaysOnTop(a.ctx, onTop)
	if onTop {
		a.db.Exec(`INSERT OR REPLACE INTO settings VALUES ('pinned', '1')`)
	} else {
		a.db.Exec(`INSERT OR REPLACE INTO settings VALUES ('pinned', '0')`)
	}
}

func (a *App) GetAlwaysOnTop() bool {
	var val string
	err := a.db.QueryRow(`SELECT value FROM settings WHERE key='pinned'`).Scan(&val)
	if err != nil {
		return false
	}
	return val == "1"
}

// Drag is handled via --wails-draggable CSS attribute on frontend

// ─── 月目标 ───

type MonthGoal struct {
	ID   string `json:"id"`
	Goal string `json:"goal"`
}

func (a *App) GetMonthGoals(year, month int) []MonthGoal {
	rows, err := a.db.Query(
		`SELECT id, goal FROM month_goals WHERE year=? AND month=? ORDER BY rowid`, year, month)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var goals []MonthGoal
	for rows.Next() {
		var g MonthGoal
		rows.Scan(&g.ID, &g.Goal)
		goals = append(goals, g)
	}
	if goals == nil {
		goals = []MonthGoal{}
	}
	return goals
}

func (a *App) SetMonthGoals(year, month int, goals []string) {
	a.db.Exec(`DELETE FROM month_goals WHERE year=? AND month=?`, year, month)
	for _, g := range goals {
		a.db.Exec(`INSERT INTO month_goals VALUES (?,?,?,?)`,
			uuid.New().String()[:12], year, month, g)
	}
}

// ─── 周任务 ───

type WeekTask struct {
	ID      string `json:"id"`
	Content string `json:"content"`
	Done    bool   `json:"done"`
}

func (a *App) GetWeekTasks(year, week int) []WeekTask {
	rows, err := a.db.Query(
		`SELECT id, content, done FROM week_tasks WHERE year=? AND week_number=? ORDER BY rowid`,
		year, week)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var tasks []WeekTask
	for rows.Next() {
		var t WeekTask
		var done int
		rows.Scan(&t.ID, &t.Content, &done)
		t.Done = done == 1
		tasks = append(tasks, t)
	}
	if tasks == nil {
		tasks = []WeekTask{}
	}
	return tasks
}

func (a *App) AddWeekTask(year, week int, content string) {
	a.db.Exec(`INSERT INTO week_tasks VALUES (?,?,?,?,0)`,
		uuid.New().String()[:12], year, week, content)
}

func (a *App) ToggleWeekTask(taskID string) {
	a.db.Exec(`UPDATE week_tasks SET done = 1 - done WHERE id=?`, taskID)
}

func (a *App) RemoveWeekTask(taskID string) {
	a.db.Exec(`DELETE FROM week_tasks WHERE id=?`, taskID)
}

// ─── 日时间块 ───

type TimeBlock struct {
	ID          string `json:"id"`
	Date        string `json:"date"`
	StartHour   int    `json:"startHour"`
	StartMinute int    `json:"startMinute"`
	Duration    int    `json:"duration"`
	Title       string `json:"title"`
	Color       string `json:"color"`
}

func (a *App) GetDayBlocks(date string) []TimeBlock {
	rows, err := a.db.Query(
		`SELECT id, date, start_hour, start_minute, duration, title, color
		 FROM day_blocks WHERE date=? ORDER BY start_hour, start_minute`, date)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var blocks []TimeBlock
	for rows.Next() {
		var b TimeBlock
		rows.Scan(&b.ID, &b.Date, &b.StartHour, &b.StartMinute, &b.Duration, &b.Title, &b.Color)
		blocks = append(blocks, b)
	}
	if blocks == nil {
		blocks = []TimeBlock{}
	}
	return blocks
}

func (a *App) AddDayBlock(date string, startHour, startMinute, duration int, title, color string) {
	a.db.Exec(`INSERT INTO day_blocks VALUES (?,?,?,?,?,?,?)`,
		uuid.New().String()[:12], date, startHour, startMinute, duration, title, color)
}

func (a *App) UpdateDayBlock(id, title, color string, startHour, startMinute, duration int) {
	a.db.Exec(`UPDATE day_blocks SET title=?, color=?, start_hour=?, start_minute=?, duration=? WHERE id=?`,
		title, color, startHour, startMinute, duration, id)
}

func (a *App) RemoveDayBlock(id string) {
	a.db.Exec(`DELETE FROM day_blocks WHERE id=?`, id)
}
