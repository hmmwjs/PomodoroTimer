# 🍅 PomodoroTimer - 高级番茄钟

一个功能丰富的番茄钟应用，帮助您提高工作效率，养成良好的时间管理习惯。本应用基于PyQt5开发，支持系统托盘操作、详细统计分析、成就系统和个性化设置。

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ 功能特性

### 核心功能
- 🍅 **标准番茄工作法**：默认25分钟工作 + 5分钟短休息 + 15分钟长休息（每4个番茄钟后）
- ⏸️ **灵活控制**：支持暂停、继续、跳过功能，适应不同工作场景
- 📝 **任务管理**：为每个番茄钟设置任务名称，追踪工作内容
- 🔔 **智能提醒**：多屏幕通知支持，确保不错过任何提醒
- 🔄 **自动工作流**：可配置的自动开始工作/休息模式
- 💾 **数据持久化**：自动保存工作数据，支持统计和分析

### 数据分析
- 📊 **详细统计**：每日、每周、每月的工作统计，直观了解工作效率
- 📈 **趋势分析**：可视化展示工作效率趋势，支持多种图表展示
- 🔍 **模式识别**：分析最高效的工作时段，优化工作时间安排
- 📋 **任务追踪**：查看各任务的时间分配，了解时间去向
- 🔮 **预测功能**：基于历史数据预测任务完成时间

### 成就系统
- 🏆 **成就解锁**：20+ 个成就等待解锁，激励持续使用
- ⭐ **等级系统**：从新手到大师的100级成长之路，指数级增长的经验值系统
- 🎯 **进度追踪**：实时查看成就完成进度，清晰的进度条展示
- 🏅 **稀有度分级**：普通、稀有、史诗、传说四个稀有度级别
- 📢 **解锁提醒**：解锁新成就时会收到通知

### 个性化设置
- ⏰ **时间调整**：灵活设置工作和休息时长，满足个人习惯
- 🎮 **调试模式**：支持短时间测试模式，便于调试和测试
- 🔊 **声音提醒**：可调节音量的声音提醒
- 💾 **数据管理**：导出/导入历史数据，数据备份和恢复

## 🚀 快速开始

### 系统要求
- Python 3.7 或更高版本
- Windows 10/11（目前仅支持Windows系统）
- 足够的磁盘空间用于数据存储

### 安装步骤

1. **克隆或下载项目**
```bash
git clone https://github.com/hmmwjs/PomodoroTimer.git
cd PomodoroTimer
```

2. **创建虚拟环境**（推荐）
```bash
python -m venv venv
# Windows
venv\Scripts\activate
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **运行应用**
```bash
# Windows
python timer.py
```

5. **打包为独立应用**（可选）
```bash
# 使用一键打包脚本
python one_click_build.py
```

## 📖 使用指南

### 基本操作
1. **开始工作**：右键点击系统托盘图标，输入任务名称，点击"开始工作"
2. **暂停/继续**：左键点击托盘图标或使用右键菜单中的"暂停"/"继续"选项
3. **跳过当前**：右键菜单 → 跳过，直接进入下一个工作/休息阶段
4. **查看统计**：右键菜单 → 统计分析，查看详细工作数据
5. **查看成就**：右键菜单 → 成就系统，查看解锁的成就和等级进度

### 进度显示
- **托盘图标**：以环形进度条方式直观显示当前剩余时间
- **颜色编码**：不同状态使用不同颜色（工作、短休息、长休息、暂停）
- **悬停提示**：将鼠标悬停在托盘图标上可查看详细信息

### 统计功能
- **今日概览**：查看今日完成的番茄数、专注时间和专注得分
- **趋势分析**：查看每周、每月的工作趋势图表
- **工作模式**：分析一天中最高效的工作时段和最常处理的任务
- **任务分布**：查看时间在不同任务上的分配情况

### 成就系统
- **成就卡片**：查看已解锁和未解锁的成就详情
- **等级进度**：查看当前等级和距离下一级所需的番茄数
- **稀有分类**：按稀有度查看不同成就

### 高级功能

#### 数据导出/备份
1. 打开设置 → 高级设置
2. 点击"导出数据"
3. 选择导出格式（CSV/JSON）和保存位置

#### 自定义提醒音
1. 在程序目录创建 `sounds` 文件夹
2. 添加以下音频文件（WAV格式）：
   - `start.wav` - 开始工作提醒音
   - `complete.wav` - 完成工作提醒音
   - `break_end.wav` - 休息结束提醒音

#### 调试模式
1. 打开设置 → 高级设置
2. 启用"调试模式"
3. 设置调试用的短时间（秒为单位）

## 📁 项目结构

```
PomodoroTimer/
├── timer.py                    # 主程序入口，包含UI和核心逻辑
├── database.py                 # 数据库管理模块，处理数据持久化
├── statistics.py               # 统计分析模块，提供数据分析功能
├── achievements.py             # 成就系统模块，管理用户成就和等级
├── multi_screen_notification.py # 多屏通知模块，支持跨屏幕通知
├── generate_sounds.py          # 声音生成模块（可选）
├── one_click_build.py          # 一键打包脚本
├── requirements.txt            # 依赖包列表
├── config.json                 # 配置文件（可编辑或自动生成）
├── timer.ico                   # 应用图标
├── LICENSE                     # 许可证文件
├── README.md                   # 项目文档
├── .gitignore                  # Git忽略文件
├── logs/                       # 日志文件夹（自动生成）
├── pomodoro_data.db            # 数据库文件（自动生成）
└── sounds/                     # 提醒音文件夹（可选）
    ├── start.wav               # 开始提醒音
    ├── complete.wav            # 完成提醒音
    └── break_end.wav           # 休息结束提醒音
```

## 🛠️ 配置选项

配置文件 `config.json` 包含以下可自定义设置：

```json
{
  "work_duration_minutes": 25,        // 工作时长（分钟）
  "short_break_minutes": 5,           // 短休息时长（分钟）
  "long_break_minutes": 15,           // 长休息时长（分钟）
  "pomodoros_until_long_break": 4,    // 长休息前的番茄钟数量
  "daily_goal": 8,                    // 每日目标番茄数
  "grid_size": 4,                     // 图标网格大小
  "notification_color": "#3a5c8b",    // 通知颜色
  "empty_color": "#6a7a96",           // 空状态颜色
  "progress_color": "#3180ff",        // 进度颜色
  "break_color": "#67e1bc",           // 休息颜色
  "pause_color": "#000000",           // 暂停背景颜色
  "pause_icon_color": "#e64f4f",      // 暂停图标颜色
  "sound_enabled": true,              // 启用声音
  "sound_volume": 50,                 // 声音音量（0-100）
  "auto_start_break": true,           // 自动开始休息
  "auto_start_work": false,           // 自动开始工作
  "minimize_to_tray": true,           // 最小化到托盘
  "debug_mode": false,                // 调试模式
  "debug_work_seconds": 10,           // 调试工作时长（秒）
  "debug_short_break_seconds": 5,     // 调试短休息时长（秒）
  "debug_long_break_seconds": 10,     // 调试长休息时长（秒）
  "completed_icon_color": "#4CAF50"   // 完成图标颜色
}
```

## 📊 数据库结构

应用使用 SQLite 数据库存储用户数据：

### 表结构

1. **sessions** - 番茄钟会话记录
   - `id`: 会话ID（主键）
   - `start_time`: 开始时间
   - `end_time`: 结束时间
   - `duration`: 持续时间（秒）
   - `task_name`: 任务名称
   - `completed`: 是否完成
   - `interruptions`: 中断次数
   - `focus_score`: 专注得分
   - `tags`: 标签（JSON格式）
   - `notes`: 备注

2. **daily_stats** - 每日统计
   - `date`: 日期（主键）
   - `total_pomodoros`: 总番茄数
   - `total_minutes`: 总分钟数
   - `avg_focus_score`: 平均专注得分
   - `completed_tasks`: 完成任务数
   - `most_productive_hour`: 最高效时段
   - `streak_days`: 连续天数

3. **achievements** - 成就数据
   - `id`: 成就ID（主键）
   - `name`: 成就名称
   - `description`: 成就描述
   - `icon`: 成就图标
   - `unlocked`: 是否解锁
   - `unlocked_date`: 解锁日期
   - `progress`: 当前进度
   - `max_progress`: 最大进度
   - `category`: 分类
   - `rarity`: 稀有度

4. **user_stats** - 用户总体统计
   - `key`: 统计键（主键）
   - `value`: 统计值
   - `updated_at`: 更新时间

## 🏆 成就系统详解

### 等级系统
- 从1级到100级，基于累计完成的番茄数
- 每升一级所需番茄数按指数增长（初始10个，每级增加15%）
- 每个等级对应不同称号，从"新手"到"时间大师"

### 成就分类

#### 数量成就
- 🌱 **初学者**：完成第一个番茄钟
- 🌿 **进阶者**：完成10个番茄钟
- 🌳 **专注达人**：完成100个番茄钟（稀有）
- 🌲 **专注大师**：完成1000个番茄钟（史诗）

#### 连续成就
- 🔥 **三日坚持**：连续3天完成番茄钟
- 💪 **周度达人**：连续7天完成番茄钟（稀有）
- 🏆 **月度英雄**：连续30天完成番茄钟（史诗）
- 👑 **年度传奇**：连续365天完成番茄钟（传说）

#### 每日成就
- ☀️ **日积月累**：完成每日目标
- 🐦 **早起鸟**：早上6点前开始第一个番茄
- 🦉 **夜猫子**：晚上10点后完成番茄
- ⭐ **完美一天**：一天内完成8个番茄钟

#### 专注成就
- 🎯 **完美专注**：完成一个无中断的番茄钟
- 🧘 **专注大师**：连续5个番茄钟无中断（稀有）
- 🌊 **深度工作**：单个任务完成10个番茄钟（稀有）

#### 特殊成就
- ⚔️ **周末战士**：周末完成10个番茄钟
- 💥 **任务粉碎机**：一天完成10个不同任务（稀有）
- 🏃 **马拉松**：累计工作100小时（史诗）

#### 里程碑成就
- ⏰ **时间旅行者**：累计专注1000小时（传说）
- 📋 **任务大师**：完成1000个任务（传说）

## 🐛 问题排查

### 常见问题与解决方案

1. **托盘图标不显示**
   - Windows: 检查任务栏设置，确保应用图标未被隐藏
   - 确保`timer.ico`文件存在于应用目录

2. **通知不显示**
   - 检查系统通知权限设置
   - 确保`screeninfo`包已正确安装
   - 尝试在设置中调整通知选项

3. **数据库错误**
   - 删除`pomodoro_data.db`文件，应用会自动重建
   - 检查是否有足够的磁盘空间
   - 确保当前用户对应用目录有写入权限

4. **应用启动失败**
   - 检查日志文件（位于`logs/`目录）
   - 确保所有依赖包都已正确安装
   - 确保Python版本符合要求（3.7+）

5. **声音提醒不工作**
   - 检查系统音量设置
   - 确保设置中启用了声音
   - 检查声音文件是否存在于`sounds/`目录

### 日志文件
应用会自动在`logs/`目录生成日志文件，格式为`pomodoro_YYYYMMDD.log`，可用于排查问题。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 代码风格
- 遵循PEP 8编码规范
- 使用类型注解提高代码可读性
- 为函数和类添加文档字符串
- 使用英文注释

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- 感谢 [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) 提供优秀的GUI框架
- 感谢 [Pomodoro Technique®](https://francescocirillo.com/pages/pomodoro-technique) 的发明者 Francesco Cirillo

## 📮 联系方式

- 作者：hmm
- Email：hmmwjs@163.com
- 项目主页：https://github.com/hmmwjs/PomodoroTimer

## 📝 备注

该项目主要工作由AI生成

---

**享受专注时光，提升工作效率！** 🍅✨
