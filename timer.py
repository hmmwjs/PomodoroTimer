#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级番茄钟 - 主程序
包含UI、系统托盘、核心计时逻辑
"""
import pdb 
import sys
import json
import os
import signal
import logging
from datetime import datetime, timedelta
from PyQt5 import QtWidgets, QtGui, QtCore
import traceback

# 设置日志
def setup_logger():
    """设置日志记录器"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"pomodoro_{datetime.now().strftime('%Y%m%d')}.log")
    
    # 创建日志记录器
    logger = logging.getLogger("PomodoroTimer")
    logger.setLevel(logging.DEBUG)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 初始化日志
logger = setup_logger()

# 导入其他模块
from database import DatabaseManager, PomodoroSession, DailyStat
from statistics import StatisticsManager, StatisticsDialog
from achievements import AchievementManager, AchievementDialog

# Windows平台特定设置
if sys.platform == 'win32':
    import ctypes
    myappid = u'AdvancedPomodoro.Timer.2.0'
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except AttributeError:
        pass

CONFIG_FILE = "config.json"
ICON_FILE = "timer.ico"

class PomodoroTrayApp(QtWidgets.QSystemTrayIcon):
    """系统托盘应用主类"""
    
    def __init__(self, parent=None):
        self.config = self.load_config()
        self.db = DatabaseManager()
        self.stats = StatisticsManager(self.db)
        self.achievements = AchievementManager(self.db)
        
        # 状态管理
        self.state = "idle"  # idle, working, short_break, long_break, paused
        self.previous_state = None  # 添加 previous_state 属性初始化
        self.remaining = 0
        self.session_start = None
        self.current_task = ""
        self.interruptions = 0
        self.daily_pomodoros = 0
        
        # 检查是否启用调试模式
        debug_mode = self.config.get("debug_mode", False)
        
        # 计时器配置
        if debug_mode:
            # 调试模式：使用秒为单位的设置
            self.work_duration = self.config.get("debug_work_seconds", 10)
            self.short_break = self.config.get("debug_short_break_seconds", 5)
            self.long_break = self.config.get("debug_long_break_seconds", 10)
            logger.info("调试模式已启用，使用秒为单位的时间设置")
        else:
            # 正常模式：使用分钟为单位的设置
            self.work_duration = int(self.config["work_duration_minutes"] * 60)
            self.short_break = int(self.config["short_break_minutes"] * 60)
            self.long_break = int(self.config["long_break_minutes"] * 60)
            
        self.pomodoros_until_long = int(self.config["pomodoros_until_long_break"])
        
        # UI配置
        self.grid_size = int(self.config["grid_size"])
        self.notification_color = self.config.get("notification_color", "#FF6B6B")
        self.empty_color = self.config.get("empty_color", "#4A5568")
        self.progress_color = self.config.get("progress_color", "#4ECDC4")
        self.break_color = self.config.get("break_color", "#95E1D3")
        self.pause_color = self.config.get("pause_color", "#FFD700")  # 暂停背景颜色
        self.pause_icon_color = self.config.get("pause_icon_color", "#FF0000")  # 暂停图标颜色
        
        # 音效设置
        self.sound_enabled = self.config.get("sound_enabled", True)
        self.sound_volume = self.config.get("sound_volume", 50)
        
        # 主计时器
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_timer)
        
        # 自动保存计时器
        self.auto_save_timer = QtCore.QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save_progress)
        self.auto_save_timer.start(30000)  # 每30秒自动保存
        
        # 初始化图标
        if os.path.exists(ICON_FILE):
            icon = QtGui.QIcon(ICON_FILE)
        else:
            # 如果图标文件不存在，创建一个简单的图标
            icon = QtGui.QIcon(self.create_idle_icon())
            # 保存图标文件以便下次使用
            pixmap = self.create_idle_icon()
            pixmap.save(ICON_FILE)
        
        super().__init__(icon, parent)
        
        # 创建菜单
        self.create_menu()
        
        # 连接点击事件
        self.activated.connect(self.handle_click)
        
        # 更新每日统计
        self.update_daily_stats()
        
        # 应用主题
        self.apply_theme()
        
        # 显示欢迎消息
        self.show_welcome_message()
        self.show()
        
        logger.info("番茄钟应用初始化完成")
    
    def create_menu(self):
        """创建右键菜单"""
        menu = QtWidgets.QMenu()
        
        # 任务输入
        self.task_action = QtWidgets.QWidgetAction(menu)
        self.task_widget = QtWidgets.QWidget()
        task_layout = QtWidgets.QHBoxLayout(self.task_widget)
        task_layout.setContentsMargins(5, 2, 5, 2)
        
        self.task_input = QtWidgets.QLineEdit()
        self.task_input.setPlaceholderText("输入任务名称...")
        self.task_input.setMaximumWidth(200)
        task_layout.addWidget(self.task_input)
        
        self.task_action.setDefaultWidget(self.task_widget)
        menu.addAction(self.task_action)
        menu.addSeparator()
        
        # 控制按钮
        self.start_action = menu.addAction("开始工作")
        self.start_action.triggered.connect(self.start_work)
        
        self.pause_action = menu.addAction("暂停")
        self.pause_action.triggered.connect(self.toggle_pause)
        self.pause_action.setEnabled(False)
        
        self.skip_action = menu.addAction("跳过")
        self.skip_action.triggered.connect(self.skip_current)
        self.skip_action.setEnabled(False)
        
        menu.addSeparator()
        
        # 功能菜单
        stats_action = menu.addAction("📊 统计分析")
        stats_action.triggered.connect(self.show_statistics)
        
        achievements_action = menu.addAction("🏆 成就系统")
        achievements_action.triggered.connect(self.show_achievements)
        
        settings_action = menu.addAction("⚙️ 设置")
        settings_action.triggered.connect(self.show_settings)
        
        menu.addSeparator()
        
        # 今日目标进度Widget
        self.daily_goal_action = QtWidgets.QWidgetAction(menu)
        self.daily_goal_widget = QtWidgets.QWidget()
        self.daily_goal_widget.setMinimumWidth(250)
        daily_goal_layout = QtWidgets.QVBoxLayout(self.daily_goal_widget)
        daily_goal_layout.setContentsMargins(10, 5, 10, 5)
        daily_goal_layout.setSpacing(3)
        
        # 今日目标标题
        self.daily_goal_title = QtWidgets.QLabel("📅 今日目标进度")
        self.daily_goal_title.setStyleSheet("font-weight: bold; color: #007bff;")
        daily_goal_layout.addWidget(self.daily_goal_title)
        
        # 今日目标进度条
        self.daily_goal_progress = QtWidgets.QProgressBar()
        self.daily_goal_progress.setTextVisible(True)
        self.daily_goal_progress.setFixedHeight(15)
        self.daily_goal_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #E0E0E0;
                border-radius: 5px;
                background-color: #F5F5F5;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4ECDC4;
                border-radius: 4px;
            }
        """)
        daily_goal_layout.addWidget(self.daily_goal_progress)
        
        # 今日目标详情
        self.daily_goal_details = QtWidgets.QLabel("0/0 个番茄")
        self.daily_goal_details.setStyleSheet("color: #666666; font-size: 9pt;")
        daily_goal_layout.addWidget(self.daily_goal_details)
        
        self.daily_goal_action.setDefaultWidget(self.daily_goal_widget)
        menu.addAction(self.daily_goal_action)
        
        # 等级进度Widget
        self.level_progress_action = QtWidgets.QWidgetAction(menu)
        self.level_progress_widget = QtWidgets.QWidget()
        self.level_progress_widget.setMinimumWidth(250)
        level_progress_layout = QtWidgets.QVBoxLayout(self.level_progress_widget)
        level_progress_layout.setContentsMargins(10, 5, 10, 5)
        level_progress_layout.setSpacing(3)
        
        # 等级进度标题
        self.level_progress_title = QtWidgets.QLabel("🏆 等级进度")
        self.level_progress_title.setStyleSheet("font-weight: bold; color: #6c5ce7;")
        level_progress_layout.addWidget(self.level_progress_title)
        
        # 等级进度条
        self.level_progress_bar = QtWidgets.QProgressBar()
        self.level_progress_bar.setTextVisible(True)
        self.level_progress_bar.setFixedHeight(15)
        self.level_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #E0E0E0;
                border-radius: 5px;
                background-color: #F5F5F5;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #9b59b6;
                border-radius: 4px;
            }
        """)
        level_progress_layout.addWidget(self.level_progress_bar)
        
        # 等级进度详情
        self.level_progress_details = QtWidgets.QLabel("等级 0")
        self.level_progress_details.setStyleSheet("color: #666666; font-size: 9pt;")
        level_progress_layout.addWidget(self.level_progress_details)
        
        self.level_progress_action.setDefaultWidget(self.level_progress_widget)
        menu.addAction(self.level_progress_action)
        
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(self.quit_app)
        
        self.setContextMenu(menu)
    
    def handle_click(self, reason):
        """处理托盘图标点击"""
        if reason == self.Trigger:
            if self.state == "idle":
                self.start_work()
            elif self.state == "paused":
                # 从暂停状态恢复
                self.toggle_pause()
            elif self.state in ["working", "short_break", "long_break"]:
                # 暂停当前状态
                self.toggle_pause()
    
    def start_work(self):
        """开始工作番茄"""
        if self.state != "idle":
            return
        
        self.current_task = self.task_input.text() or "未命名任务"
        self.state = "working"
        self.remaining = self.work_duration
        self.session_start = datetime.now()
        self.interruptions = 0
        
        self.timer.start(1000)
        self.update_menu_state()
        self.update_icon()
        
        # 显示通知
        debug_mode = self.config.get("debug_mode", False)
        if debug_mode:
            self.show_notification(
                f"🍅 开始工作: {self.current_task}",
                f"专注 {self.work_duration} 秒（调试模式）",
                3000
            )
        else:
            self.show_notification(
                f"🍅 开始工作: {self.current_task}",
                f"专注 {self.config['work_duration_minutes']} 分钟",
                3000
            )
        
        # 播放开始音效
        if self.sound_enabled:
            self.play_sound("start")
    
    def start_break(self, break_type="short"):
        """开始休息"""
        if break_type == "short":
            self.state = "short_break"
            self.remaining = self.short_break
            duration = self.short_break
            icon = "☕"
        else:
            self.state = "long_break"
            self.remaining = self.long_break
            duration = self.long_break
            icon = "🌴"
        
        self.timer.start(1000)
        self.update_menu_state()
        self.update_icon()
        
        # 显示通知
        debug_mode = self.config.get("debug_mode", False)
        if debug_mode:
            self.show_notification(
                f"{icon} 休息时间",
                f"放松一下，{duration} 秒后继续（调试模式）",
                3000
            )
        else:
            duration_minutes = self.config["short_break_minutes"] if break_type == "short" else self.config["long_break_minutes"]
            self.show_notification(
                f"{icon} 休息时间",
                f"放松一下，{duration_minutes} 分钟后继续",
                3000
            )
    
    def toggle_pause(self):
        """暂停/恢复"""
        if self.state == "paused":
            # 恢复之前的状态
            self.state = self.previous_state
            self.timer.start(1000)
            self.pause_action.setText("暂停")
        else:
            # 暂停
            self.previous_state = self.state
            self.state = "paused"
            self.timer.stop()
            self.pause_action.setText("继续")
        
        self.update_icon()
    
    def skip_current(self):
        """跳过当前番茄/休息"""
        self.timer.stop()
        
        if self.state == "working":
            # 跳过工作番茄不计入统计
            pass
        
        self.state = "idle"
        self.remaining = 0
        self.update_menu_state()
        # 将图标更新为沙漏图标
        self.setIcon(QtGui.QIcon(self.create_idle_icon()))
        
        self.setToolTip("番茄钟 - 就绪")
    
    def update_timer(self):
        """更新计时器"""
        self.remaining -= 1
        
        if self.remaining <= 0:
            self.timer.stop()
            self.complete_session()
        else:
            self.update_icon()
            self.update_tooltip()
    
    def complete_session(self):
        """完成当前会话"""
        if self.state == "working":
            # 保存工作记录
            try:
                session = PomodoroSession(
                    start_time=self.session_start,
                    end_time=datetime.now(),
                    duration=self.work_duration,
                    task_name=self.current_task,
                    completed=True,
                    interruptions=self.interruptions,
                    focus_score=self.calculate_focus_score()
                )
                
                # 保存会话
                session_id = self.db.save_session(session)
                if session_id <= 0:
                    logger.error(f"保存会话失败，返回ID: {session_id}")
                else:
                    logger.debug(f"会话保存成功，ID: {session_id}")
                
                # 更新统计
                logger.debug(f"完成番茄前：daily_pomodoros = {self.daily_pomodoros}")
                self.daily_pomodoros += 1
                logger.debug(f"完成番茄后：daily_pomodoros = {self.daily_pomodoros}, pomodoros_until_long = {self.pomodoros_until_long}")
                
                # 强制更新每日统计
                self.db._update_daily_stats(datetime.now().date())
                self.update_daily_stats()
                logger.debug(f"更新统计后：daily_pomodoros = {self.daily_pomodoros}")
                
                # 检查成就
                self.achievements.check_achievements()
            except Exception as e:
                logger.error(f"保存会话时发生错误: {e}")
                logger.exception("详细错误信息")
                # 显示错误通知
                self.show_notification(
                    "⚠️ 保存失败",
                    "保存会话数据时发生错误，但您仍可继续使用",
                    5000
                )
            
            # 决定休息类型
            # 修复：确保正确计算长休息间隔
            # 当 daily_pomodoros 能被 pomodoros_until_long 整除时，启动长休息
            is_long_break = self.daily_pomodoros > 0 and self.daily_pomodoros % self.pomodoros_until_long == 0
            logger.debug(f"休息类型判断：daily_pomodoros = {self.daily_pomodoros}, 取模 = {self.daily_pomodoros % self.pomodoros_until_long}, 是否长休息 = {is_long_break}")
            
            if is_long_break:
                self.start_break("long")
            else:
                self.start_break("short")
            
            # 播放完成音效
            if self.sound_enabled:
                self.play_sound("complete")
                
        elif self.state in ["short_break", "long_break"]:
            # 休息结束
            self.state = "idle"
            self.update_menu_state()
            # 将图标更新为沙漏图标
            self.setIcon(QtGui.QIcon(self.create_idle_icon()))
            
            self.show_notification(
                "⏰ 休息结束",
                "准备开始下一个番茄钟",
                5000
            )
            
            if self.sound_enabled:
                self.play_sound("break_end")
    
    def calculate_focus_score(self):
        """计算专注度分数"""
        base_score = 100
        interruption_penalty = self.interruptions * 10
        score = max(0, base_score - interruption_penalty)
        return score
    
    def update_icon(self):
        """更新托盘图标"""
        if self.state == "idle":
            pixmap = self.create_idle_icon()
        elif self.state == "paused":
            pixmap = self.create_paused_icon()
        elif self.state in ["working", "short_break", "long_break"]:
            progress = 1 - (self.remaining / self.get_current_duration())
            pixmap = self.create_progress_icon(progress)
        else:
            pixmap = self.create_idle_icon()
            
        
        self.setIcon(QtGui.QIcon(pixmap))
    
    def create_idle_icon(self):
        """创建空闲状态图标"""
        size = 64
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        
        # 绘制圆形背景
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtGui.QColor(self.empty_color))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(8, 8, 48, 48)
        
        # 绘制沙漏图标
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("#FFFFFF"))
        
        # 上半部分三角形
        upper_triangle = QtGui.QPolygon([
            QtCore.QPoint(24, 18),  # 左上
            QtCore.QPoint(40, 18),  # 右上
            QtCore.QPoint(32, 32),  # 中间点
        ])
        painter.drawPolygon(upper_triangle)
        
        # 下半部分三角形
        lower_triangle = QtGui.QPolygon([
            QtCore.QPoint(32, 32),  # 中间点
            QtCore.QPoint(24, 46),  # 左下
            QtCore.QPoint(40, 46),  # 右下
        ])
        painter.drawPolygon(lower_triangle)
        
        # 绘制沙漏外框
        painter.setPen(QtGui.QPen(QtGui.QColor("#FFFFFF"), 2))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawLine(24, 18, 40, 18)  # 顶部
        painter.drawLine(24, 18, 24, 46)  # 左侧
        painter.drawLine(40, 18, 40, 46)  # 右侧
        painter.drawLine(24, 46, 40, 46)  # 底部
        
        painter.end()
        return pixmap
    
    def create_progress_icon(self, progress):
        """创建进度图标"""
        size = 64
        grid = self.grid_size
        total_cells = grid * grid
        filled_cells = int(progress * total_cells)

        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)

        cell_size = size // grid
        margin = 2

        for i in range(total_cells):
            row = i // grid
            col = i % grid
            x = col * cell_size + margin
            y = row * cell_size + margin
            rect = QtCore.QRect(x, y, cell_size - 2 * margin, cell_size - 2 * margin)

            # 使用配置的颜色
            if self.state == "working":
                color = QtGui.QColor(self.progress_color) if i < filled_cells else QtGui.QColor(self.empty_color)
            else:  # 休息状态
                color = QtGui.QColor(self.break_color) if i < filled_cells else QtGui.QColor(self.empty_color)
            
            painter.fillRect(rect, color)
        
        painter.end()
        return pixmap
    
    def create_paused_icon(self):
        """创建暂停状态图标"""
        size = 64
        grid = self.grid_size
        total_cells = grid * grid
        progress = 1 - (self.remaining / self.get_current_duration())
        filled_cells = int(progress * total_cells)
        
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        
        cell_size = size // grid
        margin = 2
        
        for i in range(total_cells):
            row = i // grid
            col = i % grid
            x = col * cell_size + margin
            y = row * cell_size + margin
            rect = QtCore.QRect(x, y, cell_size - 2 * margin, cell_size - 2 * margin)
            
            # 使用暂停颜色作为背景，根据进度决定是否填充
            if i < filled_cells:
                color = QtGui.QColor(self.progress_color)
            else:
                color = QtGui.QColor(self.pause_color)
            
            painter.fillRect(rect, color)
        
        # 绘制暂停图标（类似视频播放器的暂停图标）
        painter.setBrush(QtGui.QColor(self.pause_icon_color))  # 使用暂停图标颜色
        painter.setPen(QtCore.Qt.NoPen)
        
        # 更大的两个矩形，间隔更小，更醒目的暂停图标
        rect_width = 12  # 增加宽度
        rect_spacing = 16  # 增加间隔
        rect_height = 45  # 增加高度
        center_x = size / 2
        center_y = size / 2
        
        # 左侧矩形
        left_x = center_x - rect_width - rect_spacing/2
        painter.drawRect(int(left_x), int(center_y - rect_height/2), rect_width, rect_height)
        
        # 右侧矩形
        right_x = center_x + rect_spacing/2
        painter.drawRect(int(right_x), int(center_y - rect_height/2), rect_width, rect_height)
        
        painter.end()
        return pixmap
    
    def get_current_duration(self):
        """获取当前状态的总时长"""
        if self.state == "working":
            return self.work_duration
        elif self.state == "short_break":
            return self.short_break
        elif self.state == "long_break":
            return self.long_break
        return 1
    
    def update_tooltip(self):
        """更新工具提示"""
        if self.state == "idle":
            self.setToolTip("番茄钟 - 点击开始")
        elif self.state == "paused":
            self.setToolTip("番茄钟 - 已暂停")
        else:
            minutes = self.remaining // 60
            seconds = self.remaining % 60
            state_text = {
                "working": f"工作中: {self.current_task}",
                "short_break": "短休息",
                "long_break": "长休息"
            }
            self.setToolTip(f"{state_text[self.state]} - {minutes:02d}:{seconds:02d}")
    
    def update_menu_state(self):
        """更新菜单状态"""
        is_active = self.state != "idle"
        self.start_action.setEnabled(not is_active)
        self.pause_action.setEnabled(is_active)
        self.skip_action.setEnabled(is_active)
        self.task_input.setEnabled(not is_active)
        
        # 更新今日统计和进度
        try:
            # 获取等级进度
            level_progress = self.achievements.get_level_progress()
            level = level_progress['level']
            level_percent = level_progress['progress']
            pomodoros_to_next = level_progress['pomodoros_to_next']
            
            # 计算今日目标剩余番茄数
            daily_goal = self.config.get("daily_goal", 8)
            daily_completed = self.daily_pomodoros
            remaining_today = max(0, daily_goal - daily_completed)
            daily_percent = min(100, (daily_completed / daily_goal) * 100) if daily_goal > 0 else 0
            
            # 更新今日目标进度
            self.daily_goal_title.setText(f"📅 今日目标进度 ({daily_completed}/{daily_goal})")
            self.daily_goal_progress.setRange(0, 100)
            self.daily_goal_progress.setValue(int(daily_percent))
            self.daily_goal_progress.setFormat(f"{daily_percent:.1f}%")
            
            if remaining_today > 0:
                self.daily_goal_details.setText(f"还需 {remaining_today} 个番茄完成今日目标")
            else:
                self.daily_goal_details.setText("🎉 已完成今日目标！")
            
            # 更新等级进度
            level_title = self.get_level_title(level)
            self.level_progress_title.setText(f"🏆 等级 {level} ({level_title})")
            self.level_progress_bar.setRange(0, 100)
            self.level_progress_bar.setValue(int(level_percent))
            self.level_progress_bar.setFormat(f"{level_percent:.1f}%")
            
            if pomodoros_to_next > 0:
                self.level_progress_details.setText(f"还需 {pomodoros_to_next} 个番茄升级")
            else:
                self.level_progress_details.setText("已达到最高等级！")
                
        except Exception as e:
            logger.error(f"更新菜单状态失败: {e}")
            logger.exception("详细错误信息")
            self.daily_goal_details.setText(f"今日: {self.daily_pomodoros} 个番茄")
            self.level_progress_details.setText(f"等级: {self.achievements.get_level()}")
    
    def get_level_title(self, level: int) -> str:
        """根据等级获取称号"""
        titles = [
            "番茄学徒",  # 0
            "专注新手",  # 1
            "时间管理者",  # 2
            "效率达人",  # 3
            "生产力大师",  # 4
            "番茄战士",  # 5
            "专注大师",  # 6
            "时间领主",  # 7
            "效率之王",  # 8
            "生产力传奇",  # 9
            "番茄钟神话"   # 10+
        ]
        return titles[min(level, len(titles) - 1)]
    
    def update_daily_stats(self):
        """更新每日统计"""
        today = datetime.now().date()
        try:
            stats = self.db.get_daily_stats(today)
            if stats:
                self.daily_pomodoros = stats.total_pomodoros
                logger.debug(f"更新每日统计：从数据库读取 daily_pomodoros = {self.daily_pomodoros}")
            else:
                # 如果数据库中没有今日记录，尝试强制更新
                self.db._update_daily_stats(today)
                stats = self.db.get_daily_stats(today)
                if stats:
                    self.daily_pomodoros = stats.total_pomodoros
                else:
                    self.daily_pomodoros = 0
                logger.debug(f"更新每日统计：未找到今日记录，设置 daily_pomodoros = {self.daily_pomodoros}")
            
            self.update_menu_state()
        except Exception as e:
            logger.error(f"更新每日统计失败: {e}")
            logger.exception("详细错误信息")
    
    def show_notification(self, title, message, duration=3000):
        """显示系统通知"""
        # 使用多屏通知
        try:
            from multi_screen_notification import multi_screen_notification
            multi_screen_notification(
                title, message, duration // 1000,  # 将毫秒转换为秒
                bg_color=self.notification_color,
                fg_color="#FFFFFF"
            )
        except:
            # 后备方案：使用系统托盘消息
            self.showMessage(title, message, self.Information, duration)
    
    def play_sound(self, sound_type):
        """播放音效"""
        try:
            from PyQt5 import QtMultimedia
            sound_files = {
                "start": "sounds/start.wav",
                "complete": "sounds/complete.wav",
                "break_end": "sounds/break_end.wav"
            }
            
            if sound_type in sound_files and os.path.exists(sound_files[sound_type]):
                QtMultimedia.QSound.play(sound_files[sound_type])
        except:
            pass
    
    def show_statistics(self):
        """显示统计窗口"""
        dialog = StatisticsDialog(self.stats, self)
        
        # 应用modern主题
        current_theme = "modern"
        logger.debug(f"应用主题: {current_theme} 到统计窗口")
        theme_styles = self.get_theme_styles(current_theme)
        
        # 检查theme_styles是否有效
        if not theme_styles:
            logger.error("错误: 无法获取统计窗口主题样式")
            return
        
        dialog.setStyleSheet(theme_styles["dialog"])
        
        # 更新按钮样式
        for btn in dialog.findChildren(QtWidgets.QPushButton):
            btn.setStyleSheet(theme_styles["button"])
        
        # 更新输入框样式
        for input_field in dialog.findChildren(QtWidgets.QLineEdit):
            input_field.setStyleSheet(theme_styles["input"])
            
        dialog.exec_()
    
    def show_achievements(self):
        """显示成就窗口"""
        dialog = AchievementDialog(self.achievements, self)
        
        # 应用modern主题
        current_theme = "modern"
        logger.debug(f"应用主题: {current_theme} 到成就窗口")
        theme_styles = self.get_theme_styles(current_theme)
        
        # 检查theme_styles是否有效
        if not theme_styles:
            logger.error("错误: 无法获取成就窗口主题样式")
            return
            
        dialog.setStyleSheet(theme_styles["dialog"])
        
        
        # 更新按钮样式
        for btn in dialog.findChildren(QtWidgets.QPushButton):
            btn.setStyleSheet(theme_styles["button"])
        
        # 更新输入框样式
        for input_field in dialog.findChildren(QtWidgets.QLineEdit):
            input_field.setStyleSheet(theme_styles["input"])
            
        dialog.exec_()
    
    def show_settings(self):
        """显示设置窗口"""
        dialog = SettingsDialog(self.config, self)
        
        # 应用当前主题
        # 在这里不需要手动应用主题，因为SettingsDialog的初始化已经会应用当前主题
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # 获取设置并应用
            self.config = dialog.get_settings()
            self.save_config(self.config)
            self.apply_settings()
            
            # 应用主题 - 这行其实在apply_settings中已经调用了，但为了清晰起见保留
            self.apply_theme()
            logger.info("用户更新了设置")
    
    def show_welcome_message(self):
        """显示欢迎消息"""
        level = self.achievements.get_level()
        self.show_notification(
            f"🍅 番茄钟已就绪",
            f"等级 {level} | 今日目标: {self.config.get('daily_goal', 8)} 个番茄",
            3000
        )
    
    def apply_settings(self):
        """应用新设置"""
        # 检查是否启用调试模式
        debug_mode = self.config.get("debug_mode", False)
        
        if debug_mode:
            # 调试模式：使用秒为单位的设置
            self.work_duration = self.config.get("debug_work_seconds", 10)
            self.short_break = self.config.get("debug_short_break_seconds", 5)
            self.long_break = self.config.get("debug_long_break_seconds", 10)
            print("[DEBUG] 调试模式已启用，使用秒为单位的时间设置")
        else:
            # 正常模式：使用分钟为单位的设置
            self.work_duration = int(self.config["work_duration_minutes"] * 60)
            self.short_break = int(self.config["short_break_minutes"] * 60)
            self.long_break = int(self.config["long_break_minutes"] * 60)
        
        self.pomodoros_until_long = int(self.config["pomodoros_until_long_break"])
        
        self.grid_size = int(self.config["grid_size"])
        self.notification_color = self.config.get("notification_color", "#FF6B6B")
        self.empty_color = self.config.get("empty_color", "#4A5568")
        self.progress_color = self.config.get("progress_color", "#4ECDC4")
        self.break_color = self.config.get("break_color", "#95E1D3")
        self.pause_color = self.config.get("pause_color", "#FFD700")  # 暂停背景颜色
        self.pause_icon_color = self.config.get("pause_icon_color", "#FF0000")  # 暂停图标颜色
        
        self.sound_enabled = self.config.get("sound_enabled", True)
        self.sound_volume = self.config.get("sound_volume", 50)
        
        # 应用主题
        self.apply_theme()
    
    def auto_save_progress(self):
        """自动保存进度"""
        if self.state == "working" and self.session_start:
            # 保存临时进度，以防程序崩溃
            temp_data = {
                "state": self.state,
                "remaining": self.remaining,
                "task": self.current_task,
                "session_start": self.session_start.isoformat(),
                "interruptions": self.interruptions
            }
            
            with open("temp_progress.json", "w") as f:
                json.dump(temp_data, f)
    
    def load_config(self):
        """加载配置"""
        default = {
            "work_duration_minutes": 25,
            "short_break_minutes": 5,
            "long_break_minutes": 15,
            "pomodoros_until_long_break": 4,
            "daily_goal": 8,
            "grid_size": 4,
            "notification_color": "#FF6B6B",
            "empty_color": "#4A5568", 
            "progress_color": "#4ECDC4",
            "break_color": "#95E1D3",
            "pause_color": "#FFD700",  # 暂停背景颜色
            "pause_icon_color": "#FF0000",  # 暂停图标颜色
            "sound_enabled": True,
            "sound_volume": 50,
            "auto_start_break": True,
            "auto_start_work": False,
            "minimize_to_tray": True,
            "theme": "modern",  # 固定主题为modern
            "debug_mode": False,  # 调试模式默认关闭
            "debug_work_seconds": 10,
            "debug_short_break_seconds": 5,
            "debug_long_break_seconds": 10
        }
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    user = json.load(f)
                    # 更新默认配置，但强制主题为modern
                    default.update(user)
                    default["theme"] = "modern"  # 强制使用modern主题
            except Exception as e:
                print(f"加载配置失败: {e}")
        
        return default
    
    def save_config(self, config):
        """保存配置"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def quit_app(self):
        """退出应用"""
        try:
            # 保存未完成的会话
            if self.state == "working" and self.session_start:
                session = PomodoroSession(
                    start_time=self.session_start,
                    end_time=datetime.now(),
                    duration=self.work_duration - self.remaining,
                    task_name=self.current_task,
                    completed=False,
                    interruptions=self.interruptions,
                    focus_score=self.calculate_focus_score()
                )
                try:
                    self.db.save_session(session)
                    logger.info("已保存未完成的会话")
                except Exception as e:
                    logger.error(f"保存会话失败: {e}")
            
            # 清理临时文件
            if os.path.exists("temp_progress.json"):
                try:
                    os.remove("temp_progress.json")
                    logger.debug("已删除临时进度文件")
                except Exception as e:
                    logger.error(f"删除临时文件失败: {e}")
                    
            # 关闭数据库连接
            self.db.close()
            logger.info("数据库连接已关闭")
            
        except Exception as e:
            logger.error(f"退出时发生错误: {e}")
            logger.exception("详细错误信息")
        
        logger.info("应用正在退出")
        # 确保应用退出
        QtWidgets.qApp.quit()

    def apply_theme(self):
        """应用主题"""
        # 强制使用modern主题
        current_theme = "modern"
        print(f"[DEBUG] 应用主题: {current_theme} 到托盘应用")
        theme_styles = self.get_theme_styles(current_theme)
        
        # 检查theme_styles是否有效
        if not theme_styles:
            print("[DEBUG] 错误: 无法获取主题样式")
            return
        
        # 应用主题到菜单
        if hasattr(self, "contextMenu") and self.contextMenu():
            # 确保menu样式存在
            if "menu" in theme_styles:
                self.contextMenu().setStyleSheet(theme_styles["menu"])
            else:
                print(f"[DEBUG] 警告: 主题 {current_theme} 没有menu样式")
                # 使用默认菜单样式
                self.contextMenu().setStyleSheet("""
                    QMenu {
                        background-color: #f8f9fa;
                        border: 1px solid #dee2e6;
                    }
                    QMenu::item:selected {
                        background-color: #007bff;
                        color: white;
                    }
                """)
            
            # 更新任务输入框样式
            if hasattr(self, "task_input"):
                if "input" in theme_styles:
                    self.task_input.setStyleSheet(theme_styles["input"])
                else:
                    self.task_input.setStyleSheet("QLineEdit { border: 1px solid #ced4da; }")
    
    def get_theme_styles(self, theme_name):
        """获取主题样式"""
        themes = {
            "modern": {
                "menu": """
                    QMenu {
                        background-color: #f8f9fa;
                        border: 1px solid #dee2e6;
                        border-radius: 5px;
                    }
                    QMenu::item {
                        padding: 5px 30px 5px 20px;
                        border-radius: 3px;
                    }
                    QMenu::item:selected {
                        background-color: #007bff;
                        color: white;
                    }
                    QMenu::separator {
                        height: 1px;
                        background-color: #dee2e6;
                        margin: 5px 0px;
                    }
                """,
                "dialog": """
                    QDialog {
                        background-color: #f8f9fa;
                    }
                    QTabWidget::pane {
                        border: 1px solid #dee2e6;
                        background-color: white;
                        border-radius: 5px;
                    }
                    QTabBar::tab {
                        background-color: #e9ecef;
                        color: #495057;
                        padding: 10px 20px;
                        margin-right: 2px;
                        border-top-left-radius: 4px;
                        border-top-right-radius: 4px;
                        font-size: 11pt;
                    }
                    QTabBar::tab:selected {
                        background-color: white;
                        border-bottom: 2px solid #007bff;
                        font-weight: bold;
                    }
                    QGroupBox {
                        font-weight: bold;
                        border: 2px solid #dee2e6;
                        border-radius: 5px;
                        margin-top: 1ex;
                        padding-top: 15px;
                        font-size: 10pt;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        left: 10px;
                        padding: 0 5px 0 5px;
                    }
                    QSpinBox, QDoubleSpinBox {
                        padding: 5px;
                        border: 1px solid #ced4da;
                        border-radius: 4px;
                        min-height: 25px;
                    }
                    QCheckBox {
                        font-size: 10pt;
                        min-height: 25px;
                    }
                    QLabel {
                        font-size: 10pt;
                        min-height: 20px;
                    }
                    QComboBox {
                        min-height: 30px;
                        border: 1px solid #ced4da;
                        border-radius: 4px;
                        padding: 5px;
                    }
                    QFormLayout {
                        spacing: 10px;
                    }
                    QScrollArea {
                        border: none;
                    }
                """,
                "button": """
                    QPushButton {
                        padding: 5px 15px;
                        border-radius: 4px;
                        background-color: #007bff;
                        color: white;
                        border: none;
                        min-height: 30px;
                        font-size: 10pt;
                    }
                    QPushButton:hover {
                        background-color: #0056b3;
                    }
                    QPushButton:disabled {
                        background-color: #6c757d;
                    }
                """,
                "input": """
                    QLineEdit {
                        padding: 5px;
                        border: 1px solid #ced4da;
                        border-radius: 4px;
                        background-color: white;
                        min-height: 25px;
                    }
                    QLineEdit:focus {
                        border: 1px solid #80bdff;
                        outline: 0;
                    }
                """
            },
            "classic": {
                "menu": """
                    QMenu {
                        background-color: #f0f0f0;
                        border: 1px solid #999999;
                    }
                    QMenu::item {
                        padding: 5px 30px 5px 20px;
                    }
                    QMenu::item:selected {
                        background-color: #3399ff;
                        color: white;
                    }
                    QMenu::separator {
                        height: 1px;
                        background-color: #999999;
                        margin: 5px 0px;
                    }
                """,
                "dialog": """
                    QDialog {
                        background-color: #f0f0f0;
                    }
                    QTabWidget::pane {
                        border: 1px solid #999999;
                        background-color: #f0f0f0;
                    }
                    QTabBar::tab {
                        background-color: #e0e0e0;
                        color: #333333;
                        padding: 8px 16px;
                        margin-right: 2px;
                        font-size: 10pt;
                    }
                    QTabBar::tab:selected {
                        background-color: #f0f0f0;
                        border-bottom: 2px solid #3399ff;
                    }
                    QGroupBox {
                        border: 1px solid #999999;
                        margin-top: 1ex;
                        padding-top: 15px;
                        font-size: 10pt;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        left: 10px;
                        padding: 0 5px 0 5px;
                    }
                    QSpinBox, QDoubleSpinBox {
                        padding: 3px;
                        border: 1px solid #999999;
                        min-height: 25px;
                    }
                    QCheckBox {
                        font-size: 10pt;
                        min-height: 25px;
                    }
                    QLabel {
                        font-size: 10pt;
                        min-height: 20px;
                    }
                    QComboBox {
                        min-height: 25px;
                        border: 1px solid #999999;
                        padding: 3px;
                    }
                    QFormLayout {
                        spacing: 8px;
                    }
                """,
                "button": """
                    QPushButton {
                        padding: 3px 10px;
                        background-color: #e0e0e0;
                        border: 1px solid #999999;
                        min-height: 28px;
                        font-size: 10pt;
                    }
                    QPushButton:hover {
                        background-color: #d0d0d0;
                    }
                    QPushButton:disabled {
                        background-color: #c0c0c0;
                    }
                """,
                "input": """
                    QLineEdit {
                        padding: 3px;
                        border: 1px solid #999999;
                        background-color: white;
                        min-height: 25px;
                    }
                    QLineEdit:focus {
                        border: 1px solid #3399ff;
                    }
                """
            },
            "dark": {
                "menu": """
                    QMenu {
                        background-color: #2d2d2d;
                        border: 1px solid #444444;
                        color: #f0f0f0;
                    }
                    QMenu::item {
                        padding: 5px 30px 5px 20px;
                    }
                    QMenu::item:selected {
                        background-color: #0078d7;
                        color: white;
                    }
                    QMenu::separator {
                        height: 1px;
                        background-color: #444444;
                        margin: 5px 0px;
                    }
                """,
                "dialog": """
                    QDialog {
                        background-color: #2d2d2d;
                        color: #f0f0f0;
                    }
                    QTabWidget::pane {
                        border: 1px solid #444444;
                        background-color: #2d2d2d;
                    }
                    QTabBar::tab {
                        background-color: #3d3d3d;
                        color: #f0f0f0;
                        padding: 8px 16px;
                        margin-right: 2px;
                        border-top-left-radius: 4px;
                        border-top-right-radius: 4px;
                        font-size: 10pt;
                    }
                    QTabBar::tab:selected {
                        background-color: #1e1e1e;
                        border-bottom: 2px solid #0078d7;
                    }
                    QGroupBox {
                        font-weight: bold;
                        border: 1px solid #444444;
                        border-radius: 5px;
                        margin-top: 1ex;
                        padding-top: 15px;
                        color: #f0f0f0;
                        font-size: 10pt;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        left: 10px;
                        padding: 0 5px 0 5px;
                        color: #f0f0f0;
                    }
                    QSpinBox, QDoubleSpinBox {
                        padding: 5px;
                        border: 1px solid #444444;
                        border-radius: 4px;
                        background-color: #3d3d3d;
                        color: #f0f0f0;
                        min-height: 25px;
                    }
                    QLabel {
                        color: #f0f0f0;
                        font-size: 10pt;
                        min-height: 20px;
                    }
                    QCheckBox {
                        color: #f0f0f0;
                        font-size: 10pt;
                        min-height: 25px;
                    }
                    QComboBox {
                        background-color: #3d3d3d;
                        color: #f0f0f0;
                        border: 1px solid #444444;
                        padding: 3px;
                        border-radius: 4px;
                        min-height: 28px;
                    }
                    QComboBox::drop-down {
                        subcontrol-origin: padding;
                        subcontrol-position: top right;
                        width: 15px;
                        border-left: 1px solid #444444;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #3d3d3d;
                        color: #f0f0f0;
                        border: 1px solid #444444;
                        selection-background-color: #0078d7;
                    }
                    QFormLayout {
                        spacing: 10px;
                    }
                    QWidget {
                        background-color: #2d2d2d;
                        color: #f0f0f0;
                    }
                """,
                "button": """
                    QPushButton {
                        padding: 5px 15px;
                        border-radius: 4px;
                        background-color: #0078d7;
                        color: white;
                        border: none;
                        min-height: 30px;
                        font-size: 10pt;
                    }
                    QPushButton:hover {
                        background-color: #0056b3;
                    }
                    QPushButton:disabled {
                        background-color: #444444;
                    }
                """,
                "input": """
                    QLineEdit {
                        padding: 5px;
                        border: 1px solid #444444;
                        border-radius: 4px;
                        background-color: #3d3d3d;
                        color: #f0f0f0;
                        min-height: 25px;
                    }
                    QLineEdit:focus {
                        border: 1px solid #0078d7;
                    }
                """
            }
        }
        
        # 如果主题不存在，返回现代主题
        if theme_name not in themes:
            print(f"[DEBUG] 警告: 未知主题 {theme_name}，使用默认主题")
            return themes["modern"]
        
        return themes[theme_name]


class SettingsDialog(QtWidgets.QDialog):
    """设置对话框"""
    
    def __init__(self, config, parent=None):
        # 确保 parent 是 QWidget 或 None
        parent_widget = parent.parent() if hasattr(parent, 'parent') else parent
        super().__init__(parent_widget)
        self.setWindowTitle("番茄钟设置")
        # 不再使用固定大小，而是设置最小尺寸，允许窗口根据内容自适应大小
        self.setMinimumSize(650, 600)
        self.config = config.copy()
        
        logger.debug("初始化设置对话框")
        
        # 创建选项卡
        tab_widget = QtWidgets.QTabWidget()
        tab_widget.setTabPosition(QtWidgets.QTabWidget.North)  # 确保标签在顶部
        tab_widget.setUsesScrollButtons(True)  # 启用滚动按钮，以防标签太多
        tab_widget.setElideMode(QtCore.Qt.ElideRight)  # 如果文本太长，在右侧省略
        
        # 设置标签栏样式，缩小字体并增加宽度
        tab_widget.setStyleSheet("""
            QTabBar::tab {
                font-size: 9pt;
                padding: 8px 15px;
                min-width: 80px;
                margin-right: 2px;
            }
        """)
        
        # 时间设置
        time_tab = self.create_time_tab()
        tab_widget.addTab(time_tab, "⏰ 时间设置")
        
        # 外观设置
        appearance_tab = self.create_appearance_tab()
        tab_widget.addTab(appearance_tab, "🎨 外观设置")
        
        # 声音设置
        sound_tab = self.create_sound_tab()
        tab_widget.addTab(sound_tab, "🔊 声音设置")
        
        # 高级设置
        advanced_tab = self.create_advanced_tab()
        tab_widget.addTab(advanced_tab, "⚙️ 高级设置")
        
        # 按钮
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        # 翻译确定取消按钮文字
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText("确定")
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("取消")
        
        # 设置按钮的样式
        for button in buttons.buttons():
            button.setMinimumHeight(30)
            button.setMinimumWidth(80)  # 设置最小宽度
            button.setCursor(QtCore.Qt.PointingHandCursor)  # 鼠标指针变为手型
            # 应用按钮特殊样式
            if button == buttons.button(QtWidgets.QDialogButtonBox.Ok):
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #007bff;
                        color: white;
                        border-radius: 4px;
                        padding: 5px 15px;
                    }
                    QPushButton:hover {
                        background-color: #0056b3;
                    }
                """)
        
        # 布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(tab_widget)
        layout.addWidget(buttons)
        layout.setContentsMargins(20, 20, 20, 20)  # 设置更大的边距
        layout.setSpacing(15)  # 设置组件间距
        
        # 应用当前主题样式
        self.apply_current_theme()
    
    def create_time_tab(self):
        """创建时间设置选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(20)  # 增加组件之间的间距
        
        # 工作时间
        work_group = QtWidgets.QGroupBox("工作时间")
        work_group.setMinimumHeight(80)  # 设置最小高度
        work_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        work_layout = QtWidgets.QFormLayout(work_group)
        work_layout.setVerticalSpacing(12)  # 增加表单项之间的垂直间距
        work_layout.setContentsMargins(15, 15, 15, 15)  # 设置内容边距
        
        self.work_duration_spin = QtWidgets.QSpinBox()
        self.work_duration_spin.setRange(1, 90)
        self.work_duration_spin.setValue(self.config["work_duration_minutes"])
        self.work_duration_spin.setSuffix(" 分钟")
        self.work_duration_spin.setMinimumHeight(30)  # 设置控件最小高度
        self.work_duration_spin.setMinimumWidth(100)  # 设置控件最小宽度
        work_layout.addRow("工作时长:", self.work_duration_spin)
        
        layout.addWidget(work_group)
        
        # 休息时间
        break_group = QtWidgets.QGroupBox("休息时间")
        break_group.setMinimumHeight(150)  # 设置最小高度
        break_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        break_layout = QtWidgets.QFormLayout(break_group)
        break_layout.setVerticalSpacing(12)  # 增加表单项之间的垂直间距
        break_layout.setContentsMargins(15, 15, 15, 15)  # 设置内容边距
        
        self.short_break_spin = QtWidgets.QSpinBox()
        self.short_break_spin.setRange(1, 30)
        self.short_break_spin.setValue(self.config["short_break_minutes"])
        self.short_break_spin.setSuffix(" 分钟")
        self.short_break_spin.setMinimumHeight(30)  # 设置控件最小高度
        self.short_break_spin.setMinimumWidth(100)  # 设置控件最小宽度
        break_layout.addRow("短休息:", self.short_break_spin)
        
        self.long_break_spin = QtWidgets.QSpinBox()
        self.long_break_spin.setRange(5, 60)
        self.long_break_spin.setValue(self.config["long_break_minutes"])
        self.long_break_spin.setSuffix(" 分钟")
        self.long_break_spin.setMinimumHeight(30)  # 设置控件最小高度
        self.long_break_spin.setMinimumWidth(100)  # 设置控件最小宽度
        break_layout.addRow("长休息:", self.long_break_spin)
        
        self.pomodoros_spin = QtWidgets.QSpinBox()
        self.pomodoros_spin.setRange(2, 10)
        self.pomodoros_spin.setValue(self.config["pomodoros_until_long_break"])
        self.pomodoros_spin.setSuffix(" 个番茄")
        self.pomodoros_spin.setMinimumHeight(30)  # 设置控件最小高度
        self.pomodoros_spin.setMinimumWidth(100)  # 设置控件最小宽度
        break_layout.addRow("长休息间隔:", self.pomodoros_spin)
        
        layout.addWidget(break_group)
        
        # 目标设置
        goal_group = QtWidgets.QGroupBox("每日目标")
        goal_group.setMinimumHeight(80)  # 设置最小高度
        goal_layout = QtWidgets.QFormLayout(goal_group)
        goal_layout.setVerticalSpacing(10)  # 增加表单项之间的垂直间距
        
        self.daily_goal_spin = QtWidgets.QSpinBox()
        self.daily_goal_spin.setRange(1, 20)
        self.daily_goal_spin.setValue(self.config.get("daily_goal", 8))
        self.daily_goal_spin.setSuffix(" 个番茄")
        self.daily_goal_spin.setMinimumHeight(30)  # 设置控件最小高度
        goal_layout.addRow("每日目标:", self.daily_goal_spin)
        
        layout.addWidget(goal_group)
        layout.addStretch()
        
        return widget
    
    def create_appearance_tab(self):
        """创建外观设置选项卡"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(20)  # 增加组件之间的间距
        
        # 网格大小
        grid_group = QtWidgets.QGroupBox("网格大小")
        grid_group.setMinimumHeight(80)  # 设置最小高度
        grid_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        grid_layout = QtWidgets.QVBoxLayout(grid_group)
        grid_layout.setSpacing(12)  # 增加内部组件间距
        grid_layout.setContentsMargins(15, 15, 15, 15)  # 设置内容边距
        
        self.grid_size_spin = QtWidgets.QSpinBox()
        self.grid_size_spin.setRange(2, 8)
        self.grid_size_spin.setValue(self.config.get("grid_size", 4))
        self.grid_size_spin.setSuffix(" x " + str(self.grid_size_spin.value()))
        self.grid_size_spin.setMinimumHeight(30)  # 设置控件最小高度
        self.grid_size_spin.setMinimumWidth(100)  # 设置控件最小宽度
        
        # 更新后缀显示
        def update_suffix(value):
            self.grid_size_spin.setSuffix(" x " + str(value))
        
        self.grid_size_spin.valueChanged.connect(update_suffix)
        
        grid_layout.addWidget(self.grid_size_spin)
        layout.addWidget(grid_group)
        
        # 颜色设置
        color_group = QtWidgets.QGroupBox("颜色设置")
        color_group.setMinimumHeight(280)  # 设置最小高度
        color_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        color_layout = QtWidgets.QFormLayout(color_group)
        color_layout.setVerticalSpacing(15)  # 增加表单项之间的垂直间距
        color_layout.setContentsMargins(15, 15, 15, 15)  # 设置内容边距
        color_layout.setRowWrapPolicy(QtWidgets.QFormLayout.DontWrapRows)  # 不允许行换行，保持整齐
        color_layout.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)  # 表单左对齐并垂直居中
        color_layout.setLabelAlignment(QtCore.Qt.AlignLeft)  # 标签左对齐
        
        # 通知颜色
        self.notification_color = self.config.get("notification_color", "#1c4568")
        self.notification_btn = QtWidgets.QPushButton()
        # 修改样式，确保颜色显示正确，添加!important标记
        self.notification_btn.setStyleSheet("""
            QPushButton {
                background-color: %s !important;
                border: 1px solid #888888;
                min-width: 60px;
            }
        """ % self.notification_color)
        self.notification_btn.setFixedSize(60, 30)  # 增加按钮大小
        self.notification_btn.clicked.connect(lambda: self.choose_color("notification_color"))
        self.notification_btn.setProperty("color_button", True)
        color_layout.addRow("通知颜色:", self.notification_btn)
        
        # 空格颜色
        self.empty_color = self.config.get("empty_color", "#cecece")
        self.empty_btn = QtWidgets.QPushButton()
        self.empty_btn.setStyleSheet("""
            QPushButton {
                background-color: %s !important;
                border: 1px solid #888888;
                min-width: 60px;
            }
        """ % self.empty_color)
        self.empty_btn.setFixedSize(60, 30)  # 增加按钮大小
        self.empty_btn.clicked.connect(lambda: self.choose_color("empty_color"))
        self.empty_btn.setProperty("color_button", True)
        color_layout.addRow("空格颜色:", self.empty_btn)
        
        # 进度颜色
        self.progress_color = self.config.get("progress_color", "#4ECDC4")
        self.progress_btn = QtWidgets.QPushButton()
        self.progress_btn.setStyleSheet("""
            QPushButton {
                background-color: %s !important;
                border: 1px solid #888888;
                min-width: 60px;
            }
        """ % self.progress_color)
        self.progress_btn.setFixedSize(60, 30)  # 增加按钮大小
        self.progress_btn.clicked.connect(lambda: self.choose_color("progress_color"))
        self.progress_btn.setProperty("color_button", True)
        color_layout.addRow("进度颜色:", self.progress_btn)
        
        # 休息颜色
        self.break_color = self.config.get("break_color", "#95E1D3")
        self.break_btn = QtWidgets.QPushButton()
        self.break_btn.setStyleSheet("""
            QPushButton {
                background-color: %s !important;
                border: 1px solid #888888;
                min-width: 60px;
            }
        """ % self.break_color)
        self.break_btn.setFixedSize(60, 30)  # 增加按钮大小
        self.break_btn.clicked.connect(lambda: self.choose_color("break_color"))
        self.break_btn.setProperty("color_button", True)
        color_layout.addRow("休息颜色:", self.break_btn)
        
        # 暂停颜色
        self.pause_color = self.config.get("pause_color", "#FFD700")
        self.pause_btn = QtWidgets.QPushButton()
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: %s !important;
                border: 1px solid #888888;
                min-width: 60px;
            }
        """ % self.pause_color)
        self.pause_btn.setFixedSize(60, 30)  # 增加按钮大小
        self.pause_btn.clicked.connect(lambda: self.choose_color("pause_color"))
        self.pause_btn.setProperty("color_button", True)
        color_layout.addRow("暂停背景颜色:", self.pause_btn)
        
        # 暂停图标颜色
        self.pause_icon_color = self.config.get("pause_icon_color", "#FF0000")
        self.pause_icon_btn = QtWidgets.QPushButton()
        self.pause_icon_btn.setStyleSheet("""
            QPushButton {
                background-color: %s !important;
                border: 1px solid #888888;
                min-width: 60px;
            }
        """ % self.pause_icon_color)
        self.pause_icon_btn.setFixedSize(60, 30)  # 增加按钮大小
        self.pause_icon_btn.clicked.connect(lambda: self.choose_color("pause_icon_color"))
        self.pause_icon_btn.setProperty("color_button", True)
        color_layout.addRow("暂停图标颜色:", self.pause_icon_btn)
        
        layout.addWidget(color_group)
        layout.addStretch()
        
        return tab
    
    def create_sound_tab(self):
        """创建声音设置选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(15)  # 增加组件之间的间距
        
        # 声音开关
        self.sound_enabled = QtWidgets.QCheckBox("启用声音提醒")
        self.sound_enabled.setChecked(self.config.get("sound_enabled", True))
        self.sound_enabled.setMinimumHeight(30)  # 设置控件最小高度
        layout.addWidget(self.sound_enabled)
        
        # 音量控制
        volume_group = QtWidgets.QGroupBox("音量控制")
        volume_group.setMinimumHeight(120)  # 设置最小高度
        volume_layout = QtWidgets.QFormLayout(volume_group)
        volume_layout.setVerticalSpacing(15)  # 增加表单项之间的垂直间距
        
        self.volume_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.config.get("sound_volume", 50))
        self.volume_slider.setMinimumHeight(30)  # 设置控件最小高度
        self.volume_label = QtWidgets.QLabel(f"{self.volume_slider.value()}%")
        self.volume_label.setMinimumHeight(25)  # 设置控件最小高度
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_label.setText(f"{v}%")
        )
        
        volume_layout.addRow("音量:", self.volume_slider)
        volume_layout.addRow("", self.volume_label)
        
        layout.addWidget(volume_group)
        layout.addStretch()
        
        return widget
    
    def create_advanced_tab(self):
        """创建高级设置选项卡"""
        tab = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(tab)
        main_layout.setSpacing(15)  # 增加组件之间的间距
        main_layout.setContentsMargins(15, 15, 15, 15)  # 设置内容边距
        
        # 顶部分栏容器 - 调试模式和自动化
        top_container = QtWidgets.QHBoxLayout()
        top_container.setSpacing(15)  # 横向间距
        
        # 调试模式设置 - 左侧
        debug_group = QtWidgets.QGroupBox("调试模式")
        debug_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        debug_layout = QtWidgets.QVBoxLayout(debug_group)
        debug_layout.setSpacing(12)  # 增加内部组件间距
        debug_layout.setContentsMargins(15, 15, 15, 15)  # 设置内容边距
        
        self.debug_mode = QtWidgets.QCheckBox("启用调试模式")
        self.debug_mode.setChecked(self.config.get("debug_mode", False))
        self.debug_mode.setToolTip("启用后可以设置更短的计时时间，用于测试")
        debug_layout.addWidget(self.debug_mode)
        
        # 调试模式时间设置
        debug_time_layout = QtWidgets.QFormLayout()
        debug_time_layout.setVerticalSpacing(10)  # 增加表单项之间的垂直间距
        debug_time_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)  # 允许字段增长
        debug_time_layout.setLabelAlignment(QtCore.Qt.AlignLeft)  # 标签左对齐
        debug_time_layout.setFormAlignment(QtCore.Qt.AlignLeft)  # 表单左对齐
        
        self.debug_work_seconds = QtWidgets.QSpinBox()
        self.debug_work_seconds.setRange(5, 59)
        self.debug_work_seconds.setValue(self.config.get("debug_work_seconds", 10))
        self.debug_work_seconds.setSuffix(" 秒")
        self.debug_work_seconds.setEnabled(self.config.get("debug_mode", False))
        self.debug_work_seconds.setMinimumHeight(30)  # 设置控件最小高度
        self.debug_work_seconds.setMinimumWidth(80)  # 设置最小宽度
        debug_time_layout.addRow("工作时长(调试):", self.debug_work_seconds)
        
        self.debug_short_break_seconds = QtWidgets.QSpinBox()
        self.debug_short_break_seconds.setRange(3, 30)
        self.debug_short_break_seconds.setValue(self.config.get("debug_short_break_seconds", 5))
        self.debug_short_break_seconds.setSuffix(" 秒")
        self.debug_short_break_seconds.setEnabled(self.config.get("debug_mode", False))
        self.debug_short_break_seconds.setMinimumHeight(30)  # 设置控件最小高度
        self.debug_short_break_seconds.setMinimumWidth(80)  # 设置最小宽度
        debug_time_layout.addRow("短休息(调试):", self.debug_short_break_seconds)
        
        self.debug_long_break_seconds = QtWidgets.QSpinBox()
        self.debug_long_break_seconds.setRange(5, 45)
        self.debug_long_break_seconds.setValue(self.config.get("debug_long_break_seconds", 10))
        self.debug_long_break_seconds.setSuffix(" 秒")
        self.debug_long_break_seconds.setEnabled(self.config.get("debug_mode", False))
        self.debug_long_break_seconds.setMinimumHeight(30)  # 设置控件最小高度
        self.debug_long_break_seconds.setMinimumWidth(80)  # 设置最小宽度
        debug_time_layout.addRow("长休息(调试):", self.debug_long_break_seconds)
        
        # 连接调试模式复选框与时间设置的启用状态
        self.debug_mode.toggled.connect(self.debug_work_seconds.setEnabled)
        self.debug_mode.toggled.connect(self.debug_short_break_seconds.setEnabled)
        self.debug_mode.toggled.connect(self.debug_long_break_seconds.setEnabled)
        
        debug_layout.addLayout(debug_time_layout)
        top_container.addWidget(debug_group, 60)  # 设置左侧占60%宽度
        
        # 自动化设置 - 右侧
        auto_other_container = QtWidgets.QVBoxLayout()
        
        auto_group = QtWidgets.QGroupBox("自动化")
        auto_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        auto_layout = QtWidgets.QVBoxLayout(auto_group)
        auto_layout.setSpacing(12)  # 增加内部组件间距
        auto_layout.setContentsMargins(15, 15, 15, 15)  # 设置内容边距
        
        self.auto_start_break = QtWidgets.QCheckBox("完成番茄后自动开始休息")
        self.auto_start_break.setChecked(self.config.get("auto_start_break", True))
        self.auto_start_break.setMinimumHeight(30)  # 设置控件最小高度
        auto_layout.addWidget(self.auto_start_break)
        
        self.auto_start_work = QtWidgets.QCheckBox("休息结束后自动开始工作")
        self.auto_start_work.setChecked(self.config.get("auto_start_work", False))
        self.auto_start_work.setMinimumHeight(30)  # 设置控件最小高度
        auto_layout.addWidget(self.auto_start_work)
        
        auto_other_container.addWidget(auto_group)
        
        # 其他高级设置 - 右侧
        other_group = QtWidgets.QGroupBox("其他设置")
        other_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        other_layout = QtWidgets.QVBoxLayout(other_group)
        other_layout.setSpacing(10)  # 增加内部组件间距
        other_layout.setContentsMargins(15, 15, 15, 15)  # 设置内容边距
        
        self.minimize_to_tray = QtWidgets.QCheckBox("最小化到系统托盘")
        self.minimize_to_tray.setChecked(self.config.get("minimize_to_tray", True))
        self.minimize_to_tray.setMinimumHeight(30)  # 设置控件最小高度
        other_layout.addWidget(self.minimize_to_tray)
        
        auto_other_container.addWidget(other_group)
        top_container.addLayout(auto_other_container, 40)  # 设置右侧占40%宽度
        
        main_layout.addLayout(top_container)
        
        # 底部分栏容器 - 数据管理和重置功能
        bottom_container = QtWidgets.QHBoxLayout()
        bottom_container.setSpacing(15)  # 横向间距
        
        # 数据管理 - 左侧
        data_group = QtWidgets.QGroupBox("数据管理")
        data_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        data_layout = QtWidgets.QVBoxLayout(data_group)
        data_layout.setSpacing(12)  # 增加内部组件间距
        data_layout.setContentsMargins(15, 15, 15, 15)  # 设置内容边距
        
        export_btn = QtWidgets.QPushButton("导出数据")
        export_btn.setMinimumHeight(35)  # 设置按钮最小高度
        export_btn.clicked.connect(self.export_data)
        data_layout.addWidget(export_btn)
        
        clear_btn = QtWidgets.QPushButton("清空数据")
        clear_btn.setMinimumHeight(35)  # 设置按钮最小高度
        clear_btn.clicked.connect(self.clear_data)
        data_layout.addWidget(clear_btn)
        
        bottom_container.addWidget(data_group, 1)
        
        # 添加一键重置功能 - 右侧
        reset_group = QtWidgets.QGroupBox("重置功能")
        reset_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        reset_layout = QtWidgets.QVBoxLayout(reset_group)
        reset_layout.setSpacing(12)  # 增加内部组件间距
        reset_layout.setContentsMargins(15, 15, 15, 15)  # 设置内容边距
        
        reset_config_btn = QtWidgets.QPushButton("一键重置配置")
        reset_config_btn.setMinimumHeight(35)  # 设置按钮最小高度
        reset_config_btn.setToolTip("将所有设置恢复为默认值，但保留任务数据")
        reset_config_btn.clicked.connect(self.reset_config)
        reset_layout.addWidget(reset_config_btn)
        
        reset_data_btn = QtWidgets.QPushButton("一键重置任务信息")
        reset_data_btn.setMinimumHeight(35)  # 设置按钮最小高度
        reset_data_btn.setToolTip("清除所有番茄钟记录和成就数据，但保留配置设置")
        reset_data_btn.clicked.connect(self.reset_data)
        reset_layout.addWidget(reset_data_btn)
        
        reset_all_btn = QtWidgets.QPushButton("一键重置全部")
        reset_all_btn.setMinimumHeight(35)  # 设置按钮最小高度
        reset_all_btn.setToolTip("将所有设置和数据恢复为初始状态")
        reset_all_btn.clicked.connect(self.reset_all)
        reset_layout.addWidget(reset_all_btn)
        
        bottom_container.addWidget(reset_group, 1)
        
        main_layout.addLayout(bottom_container)
        main_layout.addStretch()
        
        return tab
    
    def choose_color(self, key):
        """选择颜色"""
        current_color = QtGui.QColor(self.config.get(key, "#FFFFFF"))
        color = QtWidgets.QColorDialog.getColor(current_color, self)
        
        if color.isValid():
            self.config[key] = color.name()
            
            # 更新按钮样式，确保颜色显示正确
            style_template = """
                QPushButton {
                    background-color: %s !important;
                    border: 1px solid #888888;
                    min-width: 60px;
                }
            """
            
            # 根据不同的颜色键更新对应的按钮
            if key == "notification_color":
                self.notification_color = color.name()
                self.notification_btn.setStyleSheet(style_template % color.name())
                self.notification_btn.setProperty("color_button", True)
            elif key == "empty_color":
                self.empty_color = color.name()
                self.empty_btn.setStyleSheet(style_template % color.name())
                self.empty_btn.setProperty("color_button", True)
            elif key == "progress_color":
                self.progress_color = color.name()
                self.progress_btn.setStyleSheet(style_template % color.name())
                self.progress_btn.setProperty("color_button", True)
            elif key == "break_color":
                self.break_color = color.name()
                self.break_btn.setStyleSheet(style_template % color.name())
                self.break_btn.setProperty("color_button", True)
            elif key == "pause_color":
                self.pause_color = color.name()
                self.pause_btn.setStyleSheet(style_template % color.name())
                self.pause_btn.setProperty("color_button", True)
            elif key == "pause_icon_color":
                self.pause_icon_color = color.name()
                self.pause_icon_btn.setStyleSheet(style_template % color.name())
                self.pause_icon_btn.setProperty("color_button", True)
    
    def export_data(self):
        """导出数据"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出数据", "", "CSV Files (*.csv)"
        )
        if filename:
            # TODO: 实现数据导出
            QtWidgets.QMessageBox.information(
                self, "导出成功", f"数据已导出到: {filename}"
            )
    
    def clear_data(self):
        """清空数据"""
        reply = QtWidgets.QMessageBox.question(
            self, "确认清空",
            "确定要清空所有历史数据吗？此操作不可恢复！",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            # TODO: 实现数据清空
            QtWidgets.QMessageBox.information(
                self, "清空成功", "所有历史数据已清空"
            )
    
    def reset_config(self):
        """一键重置配置"""
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setText("确定要重置所有配置设置吗？")
        msg.setInformativeText("这将恢复所有设置为默认值，但保留您的任务数据。")
        msg.setWindowTitle("重置配置")
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        
        if msg.exec_() == QtWidgets.QMessageBox.Yes:
            logger.info("用户选择重置配置")
            # 加载默认配置
            default_config = {
                "work_duration_minutes": 25,
                "short_break_minutes": 5,
                "long_break_minutes": 15,
                "pomodoros_until_long_break": 4,
                "daily_goal": 8,
                "grid_size": 4,
                "notification_color": "#FF6B6B",
                "empty_color": "#4A5568",
                "progress_color": "#4ECDC4",
                "break_color": "#95E1D3",
                "pause_color": "#FFD700",
                "pause_icon_color": "#FF0000",
                "sound_enabled": True,
                "sound_volume": 50,
                "auto_start_break": True,
                "auto_start_work": False,
                "minimize_to_tray": True,
                "theme": "modern",  # 主题固定为modern
                "debug_mode": False,
                "debug_work_seconds": 10,
                "debug_short_break_seconds": 5,
                "debug_long_break_seconds": 10
            }
            
            try:
                # 保存默认配置
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                
                # 更新当前配置
                self.config = default_config
                
                # 获取PomodoroTrayApp对象
                tray_app = self.get_tray_app()
                if tray_app:
                    tray_app.apply_settings()
                
                # 关闭设置对话框
                self.accept()
                
                # 显示成功消息
                QtWidgets.QMessageBox.information(
                    None, 
                    "重置成功", 
                    "配置已重置为默认值。"
                )
                logger.info("配置已成功重置为默认值")
            except Exception as e:
                logger.error(f"重置配置失败: {e}")
                logger.exception("详细错误信息")
                QtWidgets.QMessageBox.critical(
                    None, 
                    "重置失败", 
                    f"重置配置时发生错误: {e}"
                )
    
    def reset_data(self):
        """一键重置任务信息"""
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setText("确定要重置所有任务数据吗？")
        msg.setInformativeText("这将删除所有番茄钟记录和成就数据，但保留您的配置设置。此操作无法撤销！")
        msg.setWindowTitle("重置数据")
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        
        if msg.exec_() == QtWidgets.QMessageBox.Yes:
            logger.info("用户选择重置任务数据")
            # 获取PomodoroTrayApp对象
            tray_app = self.get_tray_app()
            if not tray_app:
                logger.error("无法获取应用实例")
                QtWidgets.QMessageBox.critical(
                    None, 
                    "重置失败", 
                    "无法获取应用实例"
                )
                return
                
            # 清空数据库
            try:
                # 关闭数据库连接
                tray_app.db.close()
                logger.debug("已关闭数据库连接")
                
                # 删除数据库文件
                db_path = "pomodoro_data.db"
                if os.path.exists(db_path):
                    os.remove(db_path)
                    logger.debug(f"已删除数据库文件: {db_path}")
                
                # 删除WAL和SHM文件（SQLite的写入日志和共享内存文件）
                for ext in ["-wal", "-shm"]:
                    wal_path = db_path + ext
                    if os.path.exists(wal_path):
                        os.remove(wal_path)
                        logger.debug(f"已删除数据库辅助文件: {wal_path}")
                
                # 重新初始化数据库
                tray_app.db = DatabaseManager()
                
                # 更新统计和成就管理器
                tray_app.stats = StatisticsManager(tray_app.db)
                tray_app.achievements = AchievementManager(tray_app.db)
                logger.info("已重新初始化数据库和管理器")
                
                # 关闭设置对话框
                self.accept()
                
                # 显示成功消息
                QtWidgets.QMessageBox.information(
                    None, 
                    "重置成功", 
                    "所有任务数据已重置。"
                )
                logger.info("任务数据已成功重置")
                
            except Exception as e:
                logger.error(f"重置数据失败: {e}")
                logger.exception("详细错误信息")
                QtWidgets.QMessageBox.critical(
                    None, 
                    "重置失败", 
                    f"重置数据时发生错误: {e}"
                )
    
    def reset_all(self):
        """一键重置全部"""
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setText("确定要重置所有设置和数据吗？")
        msg.setInformativeText("这将恢复所有设置为默认值，并删除所有番茄钟记录和成就数据。此操作无法撤销！")
        msg.setWindowTitle("全部重置")
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        
        if msg.exec_() == QtWidgets.QMessageBox.Yes:
            logger.info("用户选择重置所有设置和数据")
            # 获取PomodoroTrayApp对象
            tray_app = self.get_tray_app()
            if not tray_app:
                logger.error("无法获取应用实例")
                QtWidgets.QMessageBox.critical(
                    None, 
                    "重置失败", 
                    "无法获取应用实例"
                )
                return
                
            # 先重置配置
            default_config = {
                "work_duration_minutes": 25,
                "short_break_minutes": 5,
                "long_break_minutes": 15,
                "pomodoros_until_long_break": 4,
                "daily_goal": 8,
                "grid_size": 4,
                "notification_color": "#FF6B6B",
                "empty_color": "#4A5568",
                "progress_color": "#4ECDC4",
                "break_color": "#95E1D3",
                "pause_color": "#FFD700",
                "pause_icon_color": "#FF0000",
                "sound_enabled": True,
                "sound_volume": 50,
                "auto_start_break": True,
                "auto_start_work": False,
                "minimize_to_tray": True,
                "theme": "modern",  # 主题固定为modern
                "debug_mode": False,
                "debug_work_seconds": 10,
                "debug_short_break_seconds": 5,
                "debug_long_break_seconds": 10
            }
            
            try:
                # 保存默认配置
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                logger.debug("已重置配置文件")
                
                # 更新当前配置
                self.config = default_config
                
                # 关闭数据库连接
                tray_app.db.close()
                logger.debug("已关闭数据库连接")
                
                # 删除数据库文件
                db_path = "pomodoro_data.db"
                if os.path.exists(db_path):
                    os.remove(db_path)
                    logger.debug(f"已删除数据库文件: {db_path}")
                
                # 删除WAL和SHM文件
                for ext in ["-wal", "-shm"]:
                    wal_path = db_path + ext
                    if os.path.exists(wal_path):
                        os.remove(wal_path)
                        logger.debug(f"已删除数据库辅助文件: {wal_path}")
                
                # 重新初始化数据库
                tray_app.db = DatabaseManager()
                
                # 更新统计和成就管理器
                tray_app.stats = StatisticsManager(tray_app.db)
                tray_app.achievements = AchievementManager(tray_app.db)
                logger.info("已重新初始化数据库和管理器")
                
                # 应用设置
                tray_app.apply_settings()
                
                # 关闭设置对话框
                self.accept()
                
                # 显示成功消息
                QtWidgets.QMessageBox.information(
                    None, 
                    "重置成功", 
                    "所有设置和数据已重置为初始状态。"
                )
                logger.info("所有设置和数据已成功重置")
                
            except Exception as e:
                logger.error(f"重置失败: {e}")
                logger.exception("详细错误信息")
                QtWidgets.QMessageBox.critical(
                    None, 
                    "重置失败", 
                    f"重置时发生错误: {e}"
                )
    
    def get_settings(self):
        """获取设置"""
        return dict(self.config, **{
            "work_duration_minutes": self.work_duration_spin.value(),
            "short_break_minutes": self.short_break_spin.value(),
            "long_break_minutes": self.long_break_spin.value(),
            "pomodoros_until_long_break": self.pomodoros_spin.value(),
            "grid_size": self.grid_size_spin.value(),
            "notification_color": self.notification_color,
            "empty_color": self.empty_color,
            "progress_color": self.progress_color,
            "break_color": self.break_color,
            "pause_color": self.pause_color,
            "pause_icon_color": self.pause_icon_color,
            "sound_enabled": self.sound_enabled.isChecked(),
            "sound_volume": self.volume_slider.value(),
            "auto_start_break": self.auto_start_break.isChecked(),
            "auto_start_work": self.auto_start_work.isChecked(),
            "minimize_to_tray": self.minimize_to_tray.isChecked(),
            "theme": "modern",  # 固定使用modern主题
            "daily_goal": self.daily_goal_spin.value(),
            # 调试模式设置
            "debug_mode": self.debug_mode.isChecked(),
            "debug_work_seconds": self.debug_work_seconds.value(),
            "debug_short_break_seconds": self.debug_short_break_seconds.value(),
            "debug_long_break_seconds": self.debug_long_break_seconds.value()
        })

    def get_tray_app(self):
        """获取PomodoroTrayApp实例"""
        # 尝试获取父窗口的tray_app属性
        if hasattr(self.parent(), 'tray_app'):
            return self.parent().tray_app
        
        # 如果父窗口就是PomodoroTrayApp
        if isinstance(self.parent(), PomodoroTrayApp):
            return self.parent()
        
        return None

    def preview_theme(self, theme_name):
        """预览主题 - 已废弃，强制使用modern主题"""
        # 强制使用modern主题
        theme_name = "modern"
        self.apply_theme_to_dialog(theme_name)
        self.config["theme"] = theme_name
    
    def apply_theme_to_dialog(self, theme_name):
        """应用主题到当前对话框 - 强制使用modern主题"""
        # 强制使用modern主题
        theme_name = "modern"
        
        # 从父应用获取主题样式
        tray_app = self.get_tray_app()
        if tray_app:
            theme_styles = tray_app.get_theme_styles(theme_name)
            self.setStyleSheet(theme_styles["dialog"])
            
            # 更新按钮样式
            for btn in self.findChildren(QtWidgets.QPushButton):
                if not btn.property("color_button"):
                    btn.setStyleSheet(theme_styles["button"])
            
            # 更新输入框样式
            for input_field in self.findChildren(QtWidgets.QLineEdit):
                input_field.setStyleSheet(theme_styles["input"])
        else:
            # 如果找不到PomodoroTrayApp对象，使用默认样式
            print("[DEBUG] 警告: 无法获取托盘应用，使用默认样式")
            self.setStyleSheet("QDialog { background-color: #f8f9fa; }")
            for btn in self.findChildren(QtWidgets.QPushButton):
                if not btn.property("color_button"):
                    btn.setStyleSheet("QPushButton { background-color: #007bff; color: white; }")
            for input_field in self.findChildren(QtWidgets.QLineEdit):
                input_field.setStyleSheet("QLineEdit { border: 1px solid #ced4da; }")

    def apply_current_theme(self):
        """应用当前主题样式 - 强制使用modern主题"""
        # 强制使用modern主题
        current_theme = "modern"
        print(f"[DEBUG] 应用主题: {current_theme} 到设置窗口")
        
        # 获取PomodoroTrayApp对象并使用其get_theme_styles方法
        tray_app = self.get_tray_app()
        if tray_app:
            theme_styles = tray_app.get_theme_styles(current_theme)
            self.setStyleSheet(theme_styles["dialog"])
            for btn in self.findChildren(QtWidgets.QPushButton):
                if not btn.property("color_button"):
                    btn.setStyleSheet(theme_styles["button"])
            for input_field in self.findChildren(QtWidgets.QLineEdit):
                input_field.setStyleSheet(theme_styles["input"])
        else:
            # 如果找不到PomodoroTrayApp对象，使用默认样式
            print("[DEBUG] 警告: 无法获取托盘应用，使用默认样式")
            self.setStyleSheet("QDialog { background-color: #f8f9fa; }")
            for btn in self.findChildren(QtWidgets.QPushButton):
                if not btn.property("color_button"):
                    btn.setStyleSheet("QPushButton { background-color: #007bff; color: white; }")
            for input_field in self.findChildren(QtWidgets.QLineEdit):
                input_field.setStyleSheet("QLineEdit { border: 1px solid #ced4da; }")

    def accept(self):
        """点击确定按钮时的处理"""
        # 保存当前设置
        new_config = self.get_settings()
        
        # 获取PomodoroTrayApp对象
        tray_app = self.get_tray_app()
        if tray_app:
            # 更新应用的配置
            tray_app.config = new_config
            tray_app.save_config(new_config)
            tray_app.apply_settings()
        
        # 关闭对话框
        super().accept()


class MainWindow(QtWidgets.QWidget):
    """主窗口（隐藏）"""
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.Tool | 
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedSize(0, 0)
        
        # 创建系统托盘
        self.tray_app = PomodoroTrayApp(self)
        
        self.hide()


def signal_handler(sig, frame):
    """处理退出信号"""
    QtWidgets.QApplication.quit()
    sys.exit(0)


def main():
    """主函数"""
    logger.info("启动番茄钟应用")
    logger.info(f"操作系统: {sys.platform}, Python版本: {sys.version}")
    
    signal.signal(signal.SIGINT, signal_handler)
    
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("高级番茄钟")
    
    # 设置应用图标
    if os.path.exists(ICON_FILE):
        app.setWindowIcon(QtGui.QIcon(ICON_FILE))
        logger.debug(f"已加载图标: {ICON_FILE}")
    else:
        logger.warning(f"图标文件不存在: {ICON_FILE}")
    
    # 创建主窗口
    window = MainWindow()
    logger.info("应用初始化完成，进入事件循环")
    
    # 启动应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
