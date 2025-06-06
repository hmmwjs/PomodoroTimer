#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成就系统模块
管理用户成就、等级和奖励
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from PyQt5 import QtWidgets, QtCore, QtGui
import math

from database import DatabaseManager, Achievement


class FlowLayout(QtWidgets.QLayout):
    """流式布局，适合展示不同高度的卡片"""
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        
        self.itemList = []
    
    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)
    
    def addItem(self, item):
        self.itemList.append(item)
    
    def count(self):
        return len(self.itemList)
    
    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None
    
    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None
    
    def expandingDirections(self):
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))
    
    def hasHeightForWidth(self):
        return True
    
    def heightForWidth(self, width):
        height = self.doLayout(QtCore.QRect(0, 0, width, 0), True)
        return height
    
    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)
    
    def sizeHint(self):
        return self.minimumSize()
    
    def minimumSize(self):
        size = QtCore.QSize()
        
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
            
        margin = self.contentsMargins()
        size += QtCore.QSize(margin.left() + margin.right(), margin.top() + margin.bottom())
        return size
    
    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        
        for item in self.itemList:
            wid = item.widget()
            spaceX = self.spacing() + wid.style().layoutSpacing(
                QtWidgets.QSizePolicy.PushButton, QtWidgets.QSizePolicy.PushButton, QtCore.Qt.Horizontal)
            spaceY = self.spacing() + wid.style().layoutSpacing(
                QtWidgets.QSizePolicy.PushButton, QtWidgets.QSizePolicy.PushButton, QtCore.Qt.Vertical)
                
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
                
            if not testOnly:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
                
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
            
        return y + lineHeight - rect.y()


class AchievementManager:
    """成就管理器"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.level_thresholds = self._init_level_thresholds()
    
    def _init_level_thresholds(self) -> List[int]:
        """初始化等级阈值"""
        # 等级所需的累计番茄数
        thresholds = [0]  # 等级0
        for level in range(1, 101):  # 等级1-100
            # 指数增长的等级需求
            required = int(10 * (1.15 ** (level - 1)))
            thresholds.append(thresholds[-1] + required)
        
        return thresholds
    
    def get_level(self) -> int:
        """获取当前等级"""
        stats = self.db.get_user_stats()
        total_pomodoros = stats.get('total_pomodoros', 0)
        
        level = 0
        for i, threshold in enumerate(self.level_thresholds):
            if total_pomodoros >= threshold:
                level = i
            else:
                break
        
        return level
    
    def get_level_progress(self) -> Dict[str, Any]:
        """获取等级进度"""
        stats = self.db.get_user_stats()
        total_pomodoros = stats.get('total_pomodoros', 0)
        current_level = self.get_level()
        
        if current_level >= len(self.level_thresholds) - 1:
            # 已达到最高等级
            return {
                'level': current_level,
                'current_exp': total_pomodoros,
                'next_level_exp': total_pomodoros,
                'progress': 100,
                'pomodoros_to_next': 0
            }
        
        current_threshold = self.level_thresholds[current_level]
        next_threshold = self.level_thresholds[current_level + 1]
        level_progress = total_pomodoros - current_threshold
        level_required = next_threshold - current_threshold
        
        return {
            'level': current_level,
            'current_exp': total_pomodoros,
            'next_level_exp': next_threshold,
            'progress': (level_progress / level_required) * 100,
            'pomodoros_to_next': next_threshold - total_pomodoros
        }
    
    def check_achievements(self) -> List[Achievement]:
        """检查并更新成就进度"""
        unlocked = []
        achievements = self.db.get_achievements()
        stats = self.db.get_user_stats()
        
        for achievement in achievements:
            if achievement.unlocked:
                continue
            
            # 检查不同类型的成就
            if self._check_achievement(achievement, stats):
                # 解锁成就
                self.db.update_achievement(achievement.id, unlocked=True)
                achievement.unlocked = True
                achievement.unlocked_date = datetime.now()
                unlocked.append(achievement)
        
        return unlocked
    
    def _check_achievement(self, achievement: Achievement, stats: Dict[str, Any]) -> bool:
        """检查特定成就是否达成"""
        achievement_id = achievement.id
        
        # 番茄数量成就
        if achievement_id == "first_pomodoro":
            return stats.get('total_pomodoros', 0) >= 1
        elif achievement_id == "ten_pomodoros":
            return stats.get('total_pomodoros', 0) >= 10
        elif achievement_id == "hundred_pomodoros":
            return stats.get('total_pomodoros', 0) >= 100
        elif achievement_id == "thousand_pomodoros":
            return stats.get('total_pomodoros', 0) >= 1000
        
        # 连续天数成就
        elif achievement_id in ["three_day_streak", "week_streak", "month_streak", "year_streak"]:
            today_stats = self.db.get_daily_stats(date.today())
            if today_stats:
                streak = today_stats.streak_days
                if achievement_id == "three_day_streak":
                    return streak >= 3
                elif achievement_id == "week_streak":
                    return streak >= 7
                elif achievement_id == "month_streak":
                    return streak >= 30
                elif achievement_id == "year_streak":
                    return streak >= 365
        
        # 每日成就
        elif achievement_id == "daily_goal":
            today_stats = self.db.get_daily_stats(date.today())
            if today_stats:
                return today_stats.total_pomodoros >= 8  # 假设每日目标是8个
        
        elif achievement_id == "perfect_day":
            today_stats = self.db.get_daily_stats(date.today())
            if today_stats:
                return today_stats.total_pomodoros >= 8
        
        # 时间相关成就
        elif achievement_id == "early_bird":
            # 检查今天是否有6点前的番茄
            sessions = self.db.get_sessions(start_date=date.today())
            for session in sessions:
                if session.completed and session.start_time.hour < 6:
                    return True
            
        elif achievement_id == "night_owl":
            # 检查今天是否有22点后的番茄
            sessions = self.db.get_sessions(start_date=date.today())
            for session in sessions:
                if session.completed and session.start_time.hour >= 22:
                    return True
        
        # 专注成就
        elif achievement_id == "perfect_focus":
            # 检查是否有无中断的番茄
            sessions = self.db.get_sessions()
            for session in sessions:
                if session.completed and session.interruptions == 0:
                    return True
        
        # 累计时间成就
        elif achievement_id == "marathon":
            total_hours = stats.get('total_hours', 0)
            return total_hours >= 100
        
        elif achievement_id == "time_traveler":
            total_hours = stats.get('total_hours', 0)
            return total_hours >= 1000
        
        # 更新进度
        self._update_achievement_progress(achievement, stats)
        
        return False
    
    def _update_achievement_progress(self, achievement: Achievement, stats: Dict[str, Any]):
        """更新成就进度"""
        progress = 0
        
        if achievement.id in ["first_pomodoro", "ten_pomodoros", "hundred_pomodoros", "thousand_pomodoros"]:
            progress = min(stats.get('total_pomodoros', 0), achievement.max_progress)
        
        elif achievement.id in ["three_day_streak", "week_streak", "month_streak", "year_streak"]:
            today_stats = self.db.get_daily_stats(date.today())
            if today_stats:
                progress = min(today_stats.streak_days, achievement.max_progress)
        
        elif achievement.id == "perfect_day":
            today_stats = self.db.get_daily_stats(date.today())
            if today_stats:
                progress = min(today_stats.total_pomodoros, achievement.max_progress)
        
        elif achievement.id == "marathon":
            total_minutes = stats.get('total_hours', 0) * 60
            progress = min(total_minutes, achievement.max_progress)
        
        elif achievement.id == "time_traveler":
            total_minutes = stats.get('total_hours', 0) * 60
            progress = min(total_minutes, achievement.max_progress)
        
        # 更新数据库中的进度
        if progress != achievement.progress:
            self.db.update_achievement(achievement.id, progress=progress)
    
    def get_unlocked_count(self) -> Dict[str, int]:
        """获取已解锁成就统计"""
        achievements = self.db.get_achievements()
        
        total = len(achievements)
        unlocked = len([a for a in achievements if a.unlocked])
        
        by_rarity = {
            'common': 0,
            'rare': 0,
            'epic': 0,
            'legendary': 0
        }
        
        for achievement in achievements:
            if achievement.unlocked:
                by_rarity[achievement.rarity] += 1
        
        return {
            'total': total,
            'unlocked': unlocked,
            'percentage': (unlocked / total * 100) if total > 0 else 0,
            'by_rarity': by_rarity
        }
    
    def get_recent_unlocks(self, days: int = 7) -> List[Achievement]:
        """获取最近解锁的成就"""
        achievements = self.db.get_achievements()
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent = []
        for achievement in achievements:
            if achievement.unlocked and achievement.unlocked_date:
                if achievement.unlocked_date >= cutoff_date:
                    recent.append(achievement)
        
        # 按解锁时间排序
        recent.sort(key=lambda x: x.unlocked_date, reverse=True)
        
        return recent
    
    def get_next_achievements(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取即将解锁的成就"""
        achievements = self.db.get_achievements()
        stats = self.db.get_user_stats()
        
        # 计算每个未解锁成就的进度
        upcoming = []
        for achievement in achievements:
            if not achievement.unlocked and achievement.max_progress > 1:
                self._update_achievement_progress(achievement, stats)
                
                progress_pct = (achievement.progress / achievement.max_progress) * 100
                if progress_pct > 0:
                    upcoming.append({
                        'achievement': achievement,
                        'progress': progress_pct,
                        'remaining': achievement.max_progress - achievement.progress
                    })
        
        # 按进度排序
        upcoming.sort(key=lambda x: x['progress'], reverse=True)
        
        return upcoming[:limit]


class AchievementDialog(QtWidgets.QDialog):
    """成就对话框"""
    
    def __init__(self, achievement_manager: AchievementManager, parent=None):
        # 确保 parent 是 QWidget 或 None
        parent_widget = parent.parent() if hasattr(parent, 'parent') else parent
        super().__init__(parent_widget)
        self.setWindowTitle("成就系统")
        self.setMinimumSize(800, 600)
        self.achievement_manager = achievement_manager
        
        # 创建布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)  # 增加组件间距
        layout.setContentsMargins(20, 20, 20, 20)  # 增加对话框内边距
        
        # 顶部等级信息
        self.create_level_info(layout)
        
        # 创建选项卡
        tab_widget = QtWidgets.QTabWidget()
        tab_widget.setDocumentMode(True)  # 使选项卡更加紧凑
        
        # 设置标签栏样式
        tab_widget.setStyleSheet("""
            QTabBar::tab {
                font-size: 10pt;
                padding: 10px 20px;
                min-width: 100px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                font-weight: bold;
            }
        """)
        
        # 成就列表选项卡
        achievements_tab = self.create_achievements_tab()
        tab_widget.addTab(achievements_tab, "🎯 成就")
        
        # 进度选项卡
        progress_tab = self.create_progress_tab()
        tab_widget.addTab(progress_tab, "📊 进度")
        
        # 排行榜选项卡（预留）
        leaderboard_tab = self.create_leaderboard_tab()
        tab_widget.addTab(leaderboard_tab, "🏅 排行榜")
        
        layout.addWidget(tab_widget)
        
        # 关闭按钮
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        close_btn.setFixedWidth(120)  # 增加按钮宽度
        close_btn.setMinimumHeight(36)  # 设置按钮高度
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)  # 鼠标指针变为手型
        layout.addWidget(close_btn, alignment=QtCore.Qt.AlignRight)
        
        # 应用样式
        self.apply_styles()
    
    def apply_styles(self):
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
                padding: 5px;
            }
            QTabBar::tab {
                background-color: #e9ecef;
                color: #495057;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 10pt;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 3px solid #007bff;
                font-weight: bold;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 16px;
                padding: 15px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: #495057;
            }
            QPushButton {
                padding: 10px 20px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0069d9;
            }
            QPushButton:pressed {
                background-color: #0062cc;
            }
            QProgressBar {
                border: 1px solid #dee2e6;
                border-radius: 5px;
                text-align: center;
                height: 18px;
                background-color: #f8f9fa;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 4px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QLabel {
                font-size: 10pt;
            }
            QTableWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                alternate-background-color: #f8f9fa;
                gridline-color: #e9ecef;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #cce5ff;
                color: #004085;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 6px;
                border: 1px solid #dee2e6;
                font-weight: bold;
                font-size: 9pt;
            }
        """)
    
    def create_level_info(self, parent_layout: QtWidgets.QVBoxLayout):
        """创建等级信息区域"""
        # 获取等级进度
        level_progress = self.achievement_manager.get_level_progress()
        
        # 创建一个现代化的渐变背景容器
        level_card = QtWidgets.QWidget()
        level_card.setFixedHeight(140)
        level_card.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                         stop:0 #4776E6, stop:1 #8E54E9);
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        """)
        
        # 主布局
        card_layout = QtWidgets.QHBoxLayout(level_card)
        card_layout.setContentsMargins(20, 15, 20, 15)
        card_layout.setSpacing(20)
        
        # 左侧奖杯容器
        trophy_container = QtWidgets.QWidget()
        trophy_container.setFixedSize(80, 80)
        trophy_container.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.15);
            border-radius: 40px;
            border: 2px solid rgba(255, 255, 255, 0.3);
        """)
        
        # 奖杯图标
        trophy_layout = QtWidgets.QVBoxLayout(trophy_container)
        trophy_layout.setContentsMargins(0, 0, 0, 0)
        
        trophy_label = QtWidgets.QLabel("🏆")
        trophy_label.setAlignment(QtCore.Qt.AlignCenter)
        trophy_label.setStyleSheet("font-size: 36px; color: white;")
        trophy_layout.addWidget(trophy_label)
        
        card_layout.addWidget(trophy_container)
        
        # 等级信息容器
        info_container = QtWidgets.QWidget()
        info_container.setStyleSheet("background: transparent;")
        info_layout = QtWidgets.QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)
        
        # 上部: 等级和称号
        header_container = QtWidgets.QWidget()
        header_container.setStyleSheet("background: transparent;")
        header_layout = QtWidgets.QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        # 等级标题
        level_label = QtWidgets.QLabel(f"等级 {level_progress['level']}")
        level_label.setStyleSheet("""
            font-size: 22px; 
            font-weight: bold; 
            color: white;
        """)
        header_layout.addWidget(level_label)
        
        # 分隔符
        separator = QtWidgets.QLabel("|")
        separator.setStyleSheet("font-size: 22px; color: rgba(255, 255, 255, 0.5);")
        header_layout.addWidget(separator)
        
        # 等级称号
        title = self.get_level_title(level_progress['level'])
        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet("""
            font-size: 16px; 
            color: rgba(255, 255, 255, 0.9);
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        
        # 进度百分比
        percent_label = QtWidgets.QLabel(f"{level_progress['progress']:.0f}%")
        percent_label.setStyleSheet("""
            font-size: 20px; 
            font-weight: bold; 
            color: white;
            background-color: rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 2px 10px;
        """)
        percent_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        header_layout.addWidget(percent_label)
        
        info_layout.addWidget(header_container)
        
        # 中部: 进度条
        progress_bar = QtWidgets.QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(int(level_progress['progress']))
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(6)
        progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 3px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: white;
                border-radius: 3px;
            }
        """)
        info_layout.addWidget(progress_bar)
        
        # 下部: 经验值信息
        exp_container = QtWidgets.QWidget()
        exp_container.setStyleSheet("background: transparent;")
        exp_layout = QtWidgets.QHBoxLayout(exp_container)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_layout.setSpacing(0)
        
        exp_current = QtWidgets.QLabel(f"{level_progress['current_exp']}")
        exp_current.setStyleSheet("font-size: 14px; color: white; font-weight: bold;")
        exp_layout.addWidget(exp_current)
        
        exp_separator = QtWidgets.QLabel(" / ")
        exp_separator.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.7);")
        exp_layout.addWidget(exp_separator)
        
        exp_next = QtWidgets.QLabel(f"{level_progress['next_level_exp']} 番茄")
        exp_next.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.7);")
        exp_layout.addWidget(exp_next)
        
        exp_layout.addStretch(1)
        
        # 距离下一级
        next_level_info = QtWidgets.QLabel(f"还需 {level_progress['pomodoros_to_next']} 个番茄升级")
        next_level_info.setStyleSheet("font-size: 13px; color: rgba(255, 255, 255, 0.6);")
        next_level_info.setAlignment(QtCore.Qt.AlignRight)
        exp_layout.addWidget(next_level_info)
        
        info_layout.addWidget(exp_container)
        
        card_layout.addWidget(info_container, 1)
        
        parent_layout.addWidget(level_card)
    
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
    
    def create_achievements_tab(self) -> QtWidgets.QWidget:
        """创建成就列表选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)
        
        # 成就统计卡片
        stats = self.achievement_manager.get_unlocked_count()
        stats_widget = QtWidgets.QWidget()
        stats_widget.setStyleSheet("""
            background-color: white;
            border: 1px solid #e9ecef;
            border-radius: 12px;
            padding: 15px;
        """)
        stats_layout = QtWidgets.QVBoxLayout(stats_widget)
        stats_layout.setContentsMargins(20, 15, 20, 15)
        stats_layout.setSpacing(15)
        
        # 进度条和百分比
        progress_container = QtWidgets.QWidget()
        progress_layout = QtWidgets.QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(10)
        
        # 百分比标签
        percent_label = QtWidgets.QLabel(f"{stats['percentage']:.1f}%")
        percent_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #6c5ce7;
        """)
        progress_layout.addWidget(percent_label)
        
        progress_bar = QtWidgets.QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(int(stats['percentage']))
        progress_bar.setFormat("")  # 不显示文字
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 6px;
                background-color: #f8f9fa;
                height: 12px;
                margin-top: 8px;
            }
            QProgressBar::chunk {
                background-color: #6c5ce7;
                border-radius: 6px;
            }
        """)
        progress_layout.addWidget(progress_bar, 1)
        
        stats_layout.addLayout(progress_layout)
        
        # 成就解锁统计
        unlock_text = QtWidgets.QLabel(
            f"已解锁: {stats['unlocked']}/{stats['total']} 个成就"
        )
        unlock_text.setAlignment(QtCore.Qt.AlignCenter)
        unlock_text.setStyleSheet("font-size: 15px; font-weight: bold; color: #495057; margin-top: 5px;")
        stats_layout.addWidget(unlock_text)
        
        # 稀有度分布
        rarity_container = QtWidgets.QWidget()
        rarity_container.setStyleSheet("""
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 10px;
        """)
        rarity_layout = QtWidgets.QHBoxLayout(rarity_container)
        rarity_layout.setSpacing(15)
        
        rarities = [
            ("普通", stats['by_rarity']['common'], "#95a5a6"),
            ("稀有", stats['by_rarity']['rare'], "#3498db"),
            ("史诗", stats['by_rarity']['epic'], "#9b59b6"),
            ("传说", stats['by_rarity']['legendary'], "#f39c12")
        ]
        
        for label, count, color in rarities:
            rarity_widget = QtWidgets.QWidget()
            rarity_layout_item = QtWidgets.QVBoxLayout(rarity_widget)
            rarity_layout_item.setContentsMargins(0, 0, 0, 0)
            rarity_layout_item.setSpacing(4)
            rarity_layout_item.setAlignment(QtCore.Qt.AlignCenter)
            
            rarity_count = QtWidgets.QLabel(str(count))
            rarity_count.setStyleSheet(f"""
                font-size: 18px; 
                font-weight: bold; 
                color: {color};
            """)
            rarity_count.setAlignment(QtCore.Qt.AlignCenter)
            rarity_layout_item.addWidget(rarity_count)
            
            rarity_label = QtWidgets.QLabel(label)
            rarity_label.setStyleSheet(f"""
                font-size: 12px; 
                color: {color};
                padding-bottom: 2px;
            """)
            rarity_label.setAlignment(QtCore.Qt.AlignCenter)
            rarity_layout_item.addWidget(rarity_label)
            
            rarity_layout.addWidget(rarity_widget)
        
        stats_layout.addWidget(rarity_container)
        layout.addWidget(stats_widget)
        
        # 成就类别选择器
        filter_container = QtWidgets.QWidget()
        filter_layout = QtWidgets.QHBoxLayout(filter_container)
        filter_layout.setContentsMargins(5, 5, 5, 5)
        filter_layout.setSpacing(10)
        
        # 类别标签
        filter_label = QtWidgets.QLabel("筛选:")
        filter_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #495057;")
        filter_layout.addWidget(filter_label)
        
        # 类别按钮
        categories = [
            ("全部", "all"),
            ("已解锁", "unlocked"),
            ("未解锁", "locked")
        ]
        
        for label, category in categories:
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)  # 单选
            
            if category == "all":
                btn.setChecked(True)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #6c5ce7;
                        color: white;
                        border: none;
                        border-radius: 15px;
                        padding: 5px 15px;
                        font-size: 13px;
                        font-weight: bold;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f8f9fa;
                        color: #495057;
                        border: 1px solid #e9ecef;
                        border-radius: 15px;
                        padding: 5px 15px;
                        font-size: 13px;
                    }
                    QPushButton:checked {
                        background-color: #6c5ce7;
                        color: white;
                        border: none;
                        font-weight: bold;
                    }
                """)
            
            filter_layout.addWidget(btn)
        
        filter_layout.addStretch(1)
        
        # 搜索框
        search_container = QtWidgets.QWidget()
        search_layout = QtWidgets.QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(5)
        
        search_box = QtWidgets.QLineEdit()
        search_box.setPlaceholderText("搜索成就...")
        search_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #e9ecef;
                border-radius: 15px;
                padding: 5px 15px;
                background-color: #f8f9fa;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #6c5ce7;
            }
        """)
        search_box.setFixedWidth(200)
        search_layout.addWidget(search_box)
        
        filter_layout.addWidget(search_container)
        
        layout.addWidget(filter_container)
        
        # 成就滚动区域
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #f0f0f0;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                min-height: 30px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        # 成就列表容器
        achievements_widget = QtWidgets.QWidget()
        achievements_layout = QtWidgets.QVBoxLayout(achievements_widget)
        achievements_layout.setSpacing(8)
        achievements_layout.setContentsMargins(5, 5, 5, 5)
        
        # 获取所有成就
        achievements = self.achievement_manager.db.get_achievements()
        
        # 按类别和稀有度排序
        achievements.sort(key=lambda x: (not x.unlocked, x.category, x.rarity))
        
        # 显示成就卡片
        for achievement in achievements:
            card = self.create_achievement_card(achievement)
            achievements_layout.addWidget(card)
        
        # 添加一些空白，确保滚动区域可以滚动到底部
        empty_widget = QtWidgets.QWidget()
        empty_widget.setMinimumHeight(20)
        achievements_layout.addWidget(empty_widget)
        
        scroll_area.setWidget(achievements_widget)
        layout.addWidget(scroll_area)
        
        return widget
    
    def create_achievement_card(self, achievement: Achievement) -> QtWidgets.QWidget:
        """创建成就卡片"""
        # 稀有度颜色映射
        rarity_colors = {
            'common': '#95A5A6',
            'rare': '#3498DB',
            'epic': '#9B59B6',
            'legendary': '#F39C12'
        }
        
        card = QtWidgets.QWidget()
        card.setFixedHeight(70)  # 固定高度，使所有卡片一致
        
        # 根据解锁状态设置样式
        border_color = rarity_colors[achievement.rarity] if achievement.unlocked else "#DEE2E6"
        bg_color = "#FFFFFF" if achievement.unlocked else "#F8F9FA"
        opacity = "1.0" if achievement.unlocked else "0.75"
        
        card.setStyleSheet(f"""
            background-color: {bg_color};
            border-left: 4px solid {border_color};
            border-radius: 8px;
            margin: 4px 0;
            opacity: {opacity};
        """)
        
        # 主布局 - 水平布局
        layout = QtWidgets.QHBoxLayout(card)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        # 图标容器（圆形背景）
        icon_container = QtWidgets.QWidget()
        icon_container.setFixedSize(40, 40)
        icon_container.setStyleSheet(f"""
            background-color: rgba({', '.join(str(int(QtGui.QColor(border_color).red() * 0.15)) for _ in range(3))}, 0.15);
            border-radius: 20px;
        """)
        
        # 图标
        icon_layout = QtWidgets.QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(0)
        
        icon_label = QtWidgets.QLabel(achievement.icon)
        icon_label.setStyleSheet(f"""
            font-size: 20px;
            color: {border_color};
        """)
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        icon_layout.addWidget(icon_label)
        
        layout.addWidget(icon_container)
        
        # 中间信息区域
        info_container = QtWidgets.QWidget()
        info_layout = QtWidgets.QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        # 成就名称
        name_label = QtWidgets.QLabel(achievement.name)
        name_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {border_color if achievement.unlocked else '#666666'};
        """)
        info_layout.addWidget(name_label)
        
        # 成就描述
        desc_label = QtWidgets.QLabel(achievement.description)
        desc_label.setStyleSheet("""
            font-size: 12px;
            color: #6C757D;
        """)
        info_layout.addWidget(desc_label)
        
        layout.addWidget(info_container, 1)
        
        # 右侧区域 - 稀有度和进度
        right_container = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        right_layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        # 稀有度标签
        rarity_text = {
            'common': '普通',
            'rare': '稀有',
            'epic': '史诗',
            'legendary': '传说'
        }
        
        rarity_label = QtWidgets.QLabel(rarity_text[achievement.rarity])
        rarity_label.setStyleSheet(f"""
            color: {border_color};
            background-color: rgba({', '.join(str(int(QtGui.QColor(border_color).red() * 0.15)) for _ in range(3))}, 0.15);
            border-radius: 10px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: bold;
        """)
        rarity_label.setAlignment(QtCore.Qt.AlignCenter)
        right_layout.addWidget(rarity_label)
        
        # 进度信息
        if achievement.max_progress > 1:
            progress_container = QtWidgets.QWidget()
            progress_layout = QtWidgets.QHBoxLayout(progress_container)
            progress_layout.setContentsMargins(0, 0, 0, 0)
            progress_layout.setSpacing(5)
            
            # 进度条
            progress_bar = QtWidgets.QProgressBar()
            progress_bar.setRange(0, int(achievement.max_progress))
            progress_bar.setValue(int(achievement.progress))
            progress_bar.setTextVisible(False)
            progress_bar.setFixedSize(60, 6)
            progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: none;
                    border-radius: 3px;
                    background-color: #F0F0F0;
                }}
                QProgressBar::chunk {{
                    background-color: {border_color};
                    border-radius: 3px;
                }}
            """)
            progress_layout.addWidget(progress_bar)
            
            # 进度文本
            progress_text = QtWidgets.QLabel(f"{int(achievement.progress)}/{int(achievement.max_progress)}")
            progress_text.setStyleSheet("""
                font-size: 11px;
                color: #6C757D;
            """)
            progress_layout.addWidget(progress_text)
            
            right_layout.addWidget(progress_container)
        elif achievement.unlocked:
            # 解锁图标和日期
            unlock_container = QtWidgets.QWidget()
            unlock_layout = QtWidgets.QHBoxLayout(unlock_container)
            unlock_layout.setContentsMargins(0, 0, 0, 0)
            unlock_layout.setSpacing(5)
            
            # 解锁图标
            unlock_icon = QtWidgets.QLabel("✓")
            unlock_icon.setStyleSheet(f"""
                font-size: 12px;
                color: {border_color};
                font-weight: bold;
            """)
            unlock_layout.addWidget(unlock_icon)
            
            # 解锁日期
            if achievement.unlocked_date:
                date_label = QtWidgets.QLabel(achievement.unlocked_date.strftime('%Y-%m-%d'))
                date_label.setStyleSheet("""
                    font-size: 11px;
                    color: #6C757D;
                """)
                unlock_layout.addWidget(date_label)
            
            right_layout.addWidget(unlock_container)
        
        layout.addWidget(right_container)
        
        return card
    
    def create_progress_tab(self) -> QtWidgets.QWidget:
        """创建进度选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)
        
        # 最近解锁
        recent_group = QtWidgets.QGroupBox("🎉 最近解锁")
        recent_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e9ecef;
                border-radius: 10px;
                margin-top: 16px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px;
                background-color: white;
                color: #495057;
            }
        """)
        recent_layout = QtWidgets.QVBoxLayout(recent_group)
        recent_layout.setSpacing(8)
        recent_layout.setContentsMargins(15, 20, 15, 15)
        
        recent_unlocks = self.achievement_manager.get_recent_unlocks(days=30)
        
        if recent_unlocks:
            for achievement in recent_unlocks[:5]:
                item_widget = QtWidgets.QWidget()
                item_widget.setStyleSheet("""
                    background-color: #f8f9fa;
                    border-radius: 8px;
                """)
                item_layout = QtWidgets.QHBoxLayout(item_widget)
                item_layout.setContentsMargins(12, 8, 12, 8)
                item_layout.setSpacing(12)
                
                # 稀有度颜色映射
                rarity_colors = {
                    'common': '#95a5a6',
                    'rare': '#3498db',
                    'epic': '#9b59b6',
                    'legendary': '#f39c12'
                }
                
                # 图标容器
                icon_container = QtWidgets.QWidget()
                icon_container.setFixedSize(36, 36)
                icon_container.setStyleSheet(f"""
                    background-color: rgba({', '.join(str(int(QtGui.QColor(rarity_colors.get(achievement.rarity, '#495057')).red() * 0.15)) for _ in range(3))}, 0.15);
                    border-radius: 18px;
                """)
                
                icon_layout = QtWidgets.QVBoxLayout(icon_container)
                icon_layout.setContentsMargins(0, 0, 0, 0)
                icon_layout.setSpacing(0)
                
                icon_label = QtWidgets.QLabel(achievement.icon)
                icon_label.setStyleSheet(f"""
                    font-size: 18px;
                    color: {rarity_colors.get(achievement.rarity, '#495057')};
                """)
                icon_label.setAlignment(QtCore.Qt.AlignCenter)
                icon_layout.addWidget(icon_label)
                
                item_layout.addWidget(icon_container)
                
                # 成就信息
                info_container = QtWidgets.QWidget()
                info_layout = QtWidgets.QVBoxLayout(info_container)
                info_layout.setContentsMargins(0, 0, 0, 0)
                info_layout.setSpacing(2)
                
                name_label = QtWidgets.QLabel(achievement.name)
                name_label.setStyleSheet(f"""
                    font-size: 13px;
                    font-weight: bold;
                    color: {rarity_colors.get(achievement.rarity, '#495057')};
                """)
                info_layout.addWidget(name_label)
                
                desc_label = QtWidgets.QLabel(achievement.description)
                desc_label.setStyleSheet("""
                    font-size: 11px;
                    color: #6c757d;
                """)
                info_layout.addWidget(desc_label)
                
                item_layout.addWidget(info_container, 1)
                
                # 解锁日期
                date_container = QtWidgets.QWidget()
                date_layout = QtWidgets.QHBoxLayout(date_container)
                date_layout.setContentsMargins(0, 0, 0, 0)
                date_layout.setSpacing(5)
                
                unlock_icon = QtWidgets.QLabel("🔓")
                unlock_icon.setStyleSheet("font-size: 12px; color: #6c757d;")
                date_layout.addWidget(unlock_icon)
                
                date_label = QtWidgets.QLabel(achievement.unlocked_date.strftime('%Y-%m-%d'))
                date_label.setStyleSheet("font-size: 12px; color: #6c757d;")
                date_layout.addWidget(date_label)
                
                item_layout.addWidget(date_container)
                
                recent_layout.addWidget(item_widget)
        else:
            no_recent = QtWidgets.QLabel("暂无最近解锁的成就")
            no_recent.setStyleSheet("color: #6c757d; font-style: italic; font-size: 14px; padding: 20px; qproperty-alignment: AlignCenter;")
            recent_layout.addWidget(no_recent)
        
        layout.addWidget(recent_group)
        
        # 即将解锁
        upcoming_group = QtWidgets.QGroupBox("🎯 即将解锁")
        upcoming_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e9ecef;
                border-radius: 10px;
                margin-top: 16px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px;
                background-color: white;
                color: #495057;
            }
        """)
        upcoming_layout = QtWidgets.QVBoxLayout(upcoming_group)
        upcoming_layout.setSpacing(8)
        upcoming_layout.setContentsMargins(15, 20, 15, 15)
        
        upcoming = self.achievement_manager.get_next_achievements(limit=5)
        
        if upcoming:
            for item in upcoming:
                achievement = item['achievement']
                progress = item['progress']
                
                item_widget = QtWidgets.QWidget()
                item_widget.setStyleSheet("""
                    background-color: #f8f9fa;
                    border-radius: 8px;
                """)
                item_layout = QtWidgets.QHBoxLayout(item_widget)
                item_layout.setContentsMargins(12, 10, 12, 10)
                item_layout.setSpacing(15)
                
                # 稀有度颜色映射
                rarity_colors = {
                    'common': '#95a5a6',
                    'rare': '#3498db',
                    'epic': '#9b59b6',
                    'legendary': '#f39c12'
                }
                
                # 图标容器
                icon_container = QtWidgets.QWidget()
                icon_container.setFixedSize(36, 36)
                icon_container.setStyleSheet(f"""
                    background-color: rgba({', '.join(str(int(QtGui.QColor(rarity_colors.get(achievement.rarity, '#495057')).red() * 0.15)) for _ in range(3))}, 0.15);
                    border-radius: 18px;
                """)
                
                icon_layout = QtWidgets.QVBoxLayout(icon_container)
                icon_layout.setContentsMargins(0, 0, 0, 0)
                icon_layout.setSpacing(0)
                
                icon_label = QtWidgets.QLabel(achievement.icon)
                icon_label.setStyleSheet(f"""
                    font-size: 18px;
                    color: {rarity_colors.get(achievement.rarity, '#495057')};
                """)
                icon_label.setAlignment(QtCore.Qt.AlignCenter)
                icon_layout.addWidget(icon_label)
                
                item_layout.addWidget(icon_container)
                
                # 成就信息
                info_container = QtWidgets.QWidget()
                info_layout = QtWidgets.QVBoxLayout(info_container)
                info_layout.setContentsMargins(0, 0, 0, 0)
                info_layout.setSpacing(5)
                
                name_label = QtWidgets.QLabel(achievement.name)
                name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
                info_layout.addWidget(name_label)
                
                desc_label = QtWidgets.QLabel(achievement.description)
                desc_label.setStyleSheet("font-size: 11px; color: #6c757d;")
                info_layout.addWidget(desc_label)
                
                # 进度条和百分比
                progress_container = QtWidgets.QWidget()
                progress_layout = QtWidgets.QHBoxLayout(progress_container)
                progress_layout.setContentsMargins(0, 0, 0, 0)
                progress_layout.setSpacing(10)
                
                progress_bar = QtWidgets.QProgressBar()
                progress_bar.setRange(0, 100)
                progress_bar.setValue(int(progress))
                progress_bar.setTextVisible(False)
                progress_bar.setFixedHeight(6)
                progress_bar.setStyleSheet(f"""
                    QProgressBar {{
                        border: none;
                        border-radius: 3px;
                        background-color: #f0f0f0;
                    }}
                    QProgressBar::chunk {{
                        background-color: {rarity_colors.get(achievement.rarity, '#28a745')};
                        border-radius: 3px;
                    }}
                """)
                progress_layout.addWidget(progress_bar, 1)
                
                progress_label = QtWidgets.QLabel(f"{progress:.1f}%")
                progress_label.setStyleSheet(f"""
                    font-size: 12px;
                    font-weight: bold;
                    color: {rarity_colors.get(achievement.rarity, '#28a745')};
                """)
                progress_layout.addWidget(progress_label)
                
                info_layout.addLayout(progress_layout)
                
                item_layout.addWidget(info_container, 1)
                
                upcoming_layout.addWidget(item_widget)
        else:
            no_upcoming = QtWidgets.QLabel("暂无即将解锁的成就")
            no_upcoming.setStyleSheet("color: #6c757d; font-style: italic; font-size: 14px; padding: 20px; qproperty-alignment: AlignCenter;")
            upcoming_layout.addWidget(no_upcoming)
        
        layout.addWidget(upcoming_group)
        layout.addStretch()
        
        return widget
    
    def create_leaderboard_tab(self) -> QtWidgets.QWidget:
        """创建排行榜选项卡（预留功能）"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建一个漂亮的即将推出界面
        coming_soon = QtWidgets.QWidget()
        coming_soon.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #667eea, stop:1 #764ba2);
            border-radius: 15px;
        """)
        coming_layout = QtWidgets.QVBoxLayout(coming_soon)
        coming_layout.setSpacing(20)
        coming_layout.setContentsMargins(30, 40, 30, 40)
        
        # 图标
        icon_label = QtWidgets.QLabel("🏆")
        icon_label.setStyleSheet("font-size: 72px; color: rgba(255, 255, 255, 0.9);")
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        coming_layout.addWidget(icon_label)
        
        # 标题
        title_label = QtWidgets.QLabel("排行榜功能即将推出！")
        title_label.setStyleSheet("font-size: 28px; color: white; font-weight: bold;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        coming_layout.addWidget(title_label)
        
        # 描述
        desc_label = QtWidgets.QLabel("敬请期待与朋友们比拼专注力的功能")
        desc_label.setStyleSheet("font-size: 16px; color: rgba(255, 255, 255, 0.8);")
        desc_label.setAlignment(QtCore.Qt.AlignCenter)
        coming_layout.addWidget(desc_label)
        
        layout.addStretch()
        layout.addWidget(coming_soon)
        layout.addStretch()
        
        return widget
