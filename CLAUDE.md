# 极简日程管理 APP

## 项目概述
Windows桌面日程管理应用，支持月/周/日三级计划视图和窗口置顶。

## 技术栈 (当前版本: Wails)
- **后端**: Go + Wails v2 (桌面应用框架)
- **前端**: 原生 HTML/CSS/JS (Vite构建)
- **数据库**: modernc.org/sqlite (纯Go实现，无CGO依赖)
- **打包**: Wails CLI，从Linux交叉编译Windows exe

## 项目结构
```
schedule-management/
├── CLAUDE.md
├── .gitignore
├── main.py                  # [旧版] Python+tkinter版本(已弃用)
├── 日程管理.exe              # 编译好的Windows可执行文件
└── wails-app/               # [当前版本] Wails应用源码
    ├── main.go              # Wails入口，窗口配置(无边框/置顶/尺寸)
    ├── app.go               # Go后端：sqlite数据库、窗口控制API、CRUD接口
    ├── go.mod / go.sum
    ├── wails.json            # Wails项目配置
    └── frontend/
        ├── index.html        # 入口HTML(自定义标题栏+内容区+弹窗层)
        ├── package.json      # Vite 5
        ├── src/
        │   ├── main.js       # 前端全部逻辑(视图渲染/事件/Go调用)
        │   └── style.css     # 极简现代风格(CSS变量主题)
        └── wailsjs/          # Wails自动生成的Go绑定
```

## 数据模型
- **month_goals**: 月目标 (year, month, goal)
- **week_tasks**: 周任务 (year, week_number, content, done)
- **day_blocks**: 日时间块 (date, start_hour, start_minute, duration, title, color)
- **settings**: 键值设置 (如置顶状态)

数据存储位置: `~/.schedule-mgmt/data.db` (sqlite)

## 构建命令
```bash
# 需要的环境:
# - Go 1.23+
# - Node.js 22+
# - Wails CLI: go install github.com/wailsapp/wails/v2/cmd/wails@latest
# - 交叉编译Windows需要: apt install gcc-mingw-w64-x86-64
# - Go代理: go env -w GOPROXY=https://goproxy.cn,direct

# 确保PATH包含正确的Node版本
export PATH=/root/.nvm/versions/node/v22.16.0/bin:$PATH:/usr/local/go/bin:/root/go/bin

# 编译Windows exe (从Linux交叉编译)
cd wails-app
wails build -platform windows/amd64
# 产物: wails-app/build/bin/日程管理.exe

# 开发模式(需要图形环境)
wails dev
```

## 关键设计决策
1. **纯Go sqlite** (modernc.org/sqlite) 而非 go-sqlite3，避免CGO交叉编译兼容性问题
2. **无边框窗口** + 自定义标题栏，通过CSS `--wails-draggable: drag` 实现拖拽
3. **前端统一通过 `callGo()` 调用后端**，内置try-catch防止异步错误中断UI流程
4. **原生JS** 无框架依赖，单文件 main.js 包含全部视图逻辑

## 历史版本
1. Electron + Vue 3 + Vite (已废弃，Linux无法交叉编译Windows)
2. Python + tkinter + sqlite3 (main.py，可用但UI较简陋)
3. **Go + Wails** (当前版本，14MB exe，现代Web UI)
