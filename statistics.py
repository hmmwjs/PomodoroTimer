#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计分析模块
提供数据分析和可视化功能
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple
import math
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtChart import (QChart, QChartView, QLineSeries, QBarSeries, QBarSet,
                          QPieSeries, QValueAxis, QBarCategoryAxis, QDateTimeAxis)

from database import DatabaseManager, PomodoroSession, DailyStat


class StatisticsManager:
    """统计管理器"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def get_today_stats(self) -> Dict[str, Any]:
        """获取今日统计"""
        today = date.today()
        stats = self.db.get_daily_stats(today)
        
        if stats:
            return {
                'pomodoros': stats.total_pomodoros,
                'minutes': stats.total_minutes,
                'focus_score': stats.avg_focus_score,
                'tasks': stats.completed_tasks,
                'productive_hour': stats.most_productive_hour,
                'streak': stats.streak_days
            }
        
        return {
            'pomodoros': 0,
            'minutes': 0,
            'focus_score': 0,
            'tasks': 0,
            'productive_hour': None,
            'streak': 0
        }
    
    def get_week_stats(self) -> Dict[str, Any]:
        """获取本周统计"""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        daily_stats = self.db.get_stats_range(week_start, week_end)
        
        total_pomodoros = sum(s.total_pomodoros for s in daily_stats)
        total_minutes = sum(s.total_minutes for s in daily_stats)
        avg_focus = sum(s.avg_focus_score for s in daily_stats) / len(daily_stats) if daily_stats else 0
        
        # 每日分布
        daily_distribution = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            stat = next((s for s in daily_stats if s.date == day), None)
            daily_distribution.append({
                'day': day.strftime('%a'),
                'pomodoros': stat.total_pomodoros if stat else 0,
                'minutes': stat.total_minutes if stat else 0
            })
        
        return {
            'total_pomodoros': total_pomodoros,
            'total_minutes': total_minutes,
            'avg_focus': avg_focus,
            'daily_distribution': daily_distribution,
            'best_day': max(daily_stats, key=lambda x: x.total_pomodoros).date if daily_stats else None
        }
    
    def get_month_stats(self) -> Dict[str, Any]:
        """获取本月统计"""
        today = date.today()
        month_start = date(today.year, today.month, 1)
        
        # 计算月末
        if today.month == 12:
            month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        
        daily_stats = self.db.get_stats_range(month_start, month_end)
        
        total_pomodoros = sum(s.total_pomodoros for s in daily_stats)
        total_hours = sum(s.total_minutes for s in daily_stats) / 60
        
        # 计算工作天数
        work_days = len([s for s in daily_stats if s.total_pomodoros > 0])
        
        # 每周趋势
        weekly_trend = self._calculate_weekly_trend(daily_stats)
        
        return {
            'total_pomodoros': total_pomodoros,
            'total_hours': total_hours,
            'work_days': work_days,
            'avg_daily': total_pomodoros / work_days if work_days > 0 else 0,
            'weekly_trend': weekly_trend,
            'completion_rate': (work_days / today.day) * 100 if today.day > 0 else 0
        }
    
    def get_productivity_patterns(self) -> Dict[str, Any]:
        """分析生产力模式"""
        # 获取最近30天的会话数据
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        sessions = self.db.get_sessions(start_date, end_date)
        
        # 按小时分组
        hourly_distribution = {}
        for hour in range(24):
            hourly_distribution[hour] = {'count': 0, 'avg_focus': 0}
        
        for session in sessions:
            if session.completed:
                hour = session.start_time.hour
                hourly_distribution[hour]['count'] += 1
                hourly_distribution[hour]['avg_focus'] += session.focus_score
        
        # 计算平均值
        for hour in hourly_distribution:
            count = hourly_distribution[hour]['count']
            if count > 0:
                hourly_distribution[hour]['avg_focus'] /= count
        
        # 找出最高效的时间段
        productive_hours = sorted(
            hourly_distribution.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:3]
        
        # 按星期几分组
        weekday_distribution = {}
        for i in range(7):
            weekday_distribution[i] = 0
        
        for session in sessions:
            if session.completed:
                weekday_distribution[session.start_time.weekday()] += 1
        
        return {
            'hourly_distribution': hourly_distribution,
            'productive_hours': productive_hours,
            'weekday_distribution': weekday_distribution,
            'total_sessions': len([s for s in sessions if s.completed])
        }
    
    def get_task_analysis(self) -> Dict[str, Any]:
        """任务分析"""
        task_stats = self.db.get_task_stats(limit=20)
        
        # 计算总时间
        total_hours = sum(task['hours'] for task in task_stats)
        
        # 为每个任务计算百分比
        for task in task_stats:
            task['percentage'] = (task['hours'] / total_hours * 100) if total_hours > 0 else 0
        
        # 找出最专注的任务
        most_focused = max(task_stats, key=lambda x: x['avg_focus']) if task_stats else None
        
        # 找出最耗时的任务
        most_time = max(task_stats, key=lambda x: x['hours']) if task_stats else None
        
        return {
            'tasks': task_stats[:10],  # 前10个任务
            'total_tasks': len(task_stats),
            'most_focused': most_focused,
            'most_time': most_time,
            'total_hours': total_hours
        }
    
    def _calculate_weekly_trend(self, daily_stats: List[DailyStat]) -> List[Dict[str, Any]]:
        """计算每周趋势"""
        weekly_data = {}
        
        for stat in daily_stats:
            week_num = stat.date.isocalendar()[1]
            if week_num not in weekly_data:
                weekly_data[week_num] = {
                    'pomodoros': 0,
                    'minutes': 0,
                    'days': 0
                }
            
            weekly_data[week_num]['pomodoros'] += stat.total_pomodoros
            weekly_data[week_num]['minutes'] += stat.total_minutes
            weekly_data[week_num]['days'] += 1
        
        # 转换为列表
        trend = []
        for week_num, data in sorted(weekly_data.items()):
            trend.append({
                'week': f"第{week_num}周",
                'pomodoros': data['pomodoros'],
                'minutes': data['minutes'],
                'avg_daily': data['pomodoros'] / data['days'] if data['days'] > 0 else 0
            })
        
        return trend
    
    def predict_completion_time(self, remaining_pomodoros: int) -> Dict[str, Any]:
        """预测完成时间"""
        # 获取最近7天的平均完成率
        today = date.today()
        week_ago = today - timedelta(days=7)
        daily_stats = self.db.get_stats_range(week_ago, today)
        
        if not daily_stats:
            return {
                'estimated_days': None,
                'estimated_date': None,
                'confidence': 0
            }
        
        # 计算平均每日番茄数
        total_pomodoros = sum(s.total_pomodoros for s in daily_stats)
        avg_daily = total_pomodoros / len(daily_stats)
        
        if avg_daily == 0:
            return {
                'estimated_days': None,
                'estimated_date': None,
                'confidence': 0
            }
        
        # 预测天数
        estimated_days = math.ceil(remaining_pomodoros / avg_daily)
        estimated_date = today + timedelta(days=estimated_days)
        
        # 计算置信度（基于数据的一致性）
        variance = sum((s.total_pomodoros - avg_daily) ** 2 for s in daily_stats) / len(daily_stats)
        std_dev = math.sqrt(variance)
        confidence = max(0, min(100, 100 - (std_dev / avg_daily * 100))) if avg_daily > 0 else 0
        
        return {
            'estimated_days': estimated_days,
            'estimated_date': estimated_date,
            'confidence': confidence,
            'avg_daily': avg_daily
        }


class StatisticsDialog(QtWidgets.QDialog):
    """统计对话框"""
    
    def __init__(self, stats_manager: StatisticsManager, parent=None):
        # 确保 parent 是 QWidget 或 None
        parent_widget = parent.parent() if hasattr(parent, 'parent') else parent
        super().__init__(parent_widget)
        self.setWindowTitle("统计分析")
        self.setMinimumSize(900, 700)
        self.stats = stats_manager
        
        # 创建布局
        layout = QtWidgets.QVBoxLayout(self)
        
        # 创建选项卡
        self.tab_widget = QtWidgets.QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 添加各个选项卡
        self.create_overview_tab()
        self.create_trends_tab()
        self.create_patterns_tab()
        self.create_tasks_tab()
        
        # 关闭按钮
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.close)
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
                background-color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e9ecef;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            .stat-value {
                font-size: 24px;
                font-weight: bold;
                color: #495057;
            }
            .stat-label {
                font-size: 12px;
                color: #6c757d;
            }
            QPushButton {
                padding: 8px 16px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
    
    def create_overview_tab(self):
        """创建概览选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # 今日统计
        today_group = QtWidgets.QGroupBox("今日统计")
        today_layout = QtWidgets.QGridLayout(today_group)
        
        today_stats = self.stats.get_today_stats()
        
        # 创建统计卡片
        cards = [
            ("番茄数", str(today_stats['pomodoros']), "🍅"),
            ("专注时间", f"{today_stats['minutes']} 分钟", "⏱️"),
            ("专注度", f"{today_stats['focus_score']:.1f}%", "🎯"),
            ("连续天数", f"{today_stats['streak']} 天", "🔥")
        ]
        
        for i, (label, value, icon) in enumerate(cards):
            card = self.create_stat_card(label, value, icon)
            today_layout.addWidget(card, 0, i)
        
        layout.addWidget(today_group)
        
        # 本周统计
        week_group = QtWidgets.QGroupBox("本周统计")
        week_layout = QtWidgets.QVBoxLayout(week_group)
        
        week_stats = self.stats.get_week_stats()
        
        # 创建周统计图表
        week_chart = self.create_week_chart(week_stats['daily_distribution'])
        week_layout.addWidget(week_chart)
        
        # 周统计摘要
        week_summary = QtWidgets.QLabel(
            f"本周完成: {week_stats['total_pomodoros']} 个番茄 | "
            f"总时长: {week_stats['total_minutes']} 分钟 | "
            f"平均专注度: {week_stats['avg_focus']:.1f}%"
        )
        week_summary.setAlignment(QtCore.Qt.AlignCenter)
        week_layout.addWidget(week_summary)
        
        layout.addWidget(week_group)
        
        # 用户总体统计
        overall_group = QtWidgets.QGroupBox("总体统计")
        overall_layout = QtWidgets.QGridLayout(overall_group)
        
        user_stats = self.stats.db.get_user_stats()
        
        overall_cards = [
            ("总番茄数", str(user_stats.get('total_pomodoros', 0)), "🍅"),
            ("总时长", f"{user_stats.get('total_hours', 0):.1f} 小时", "⏰"),
            ("任务数", str(user_stats.get('total_tasks', 0)), "📋"),
            ("最长连续", f"{user_stats.get('max_streak', 0)} 天", "🏆")
        ]
        
        for i, (label, value, icon) in enumerate(overall_cards):
            card = self.create_stat_card(label, value, icon)
            overall_layout.addWidget(card, 0, i)
        
        layout.addWidget(overall_group)
        
        self.tab_widget.addTab(widget, "📊 概览")
    
    def create_trends_tab(self):
        """创建趋势选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # 月度趋势
        month_stats = self.stats.get_month_stats()
        
        # 月度统计卡片
        month_info = QtWidgets.QGroupBox("本月统计")
        month_layout = QtWidgets.QHBoxLayout(month_info)
        
        month_cards = [
            ("总番茄", str(month_stats['total_pomodoros'])),
            ("总时长", f"{month_stats['total_hours']:.1f} 小时"),
            ("工作天数", f"{month_stats['work_days']} 天"),
            ("日均", f"{month_stats['avg_daily']:.1f} 个"),
            ("完成率", f"{month_stats['completion_rate']:.1f}%")
        ]
        
        for label, value in month_cards:
            card = QtWidgets.QWidget()
            card_layout = QtWidgets.QVBoxLayout(card)
            
            value_label = QtWidgets.QLabel(value)
            value_label.setProperty("class", "stat-value")
            value_label.setAlignment(QtCore.Qt.AlignCenter)
            
            label_label = QtWidgets.QLabel(label)
            label_label.setProperty("class", "stat-label")
            label_label.setAlignment(QtCore.Qt.AlignCenter)
            
            card_layout.addWidget(value_label)
            card_layout.addWidget(label_label)
            
            month_layout.addWidget(card)
        
        layout.addWidget(month_info)
        
        # 趋势图表
        if month_stats['weekly_trend']:
            trend_chart = self.create_trend_chart(month_stats['weekly_trend'])
            layout.addWidget(trend_chart)
        
        self.tab_widget.addTab(widget, "📈 趋势")
    
    def create_patterns_tab(self):
        """创建模式分析选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        patterns = self.stats.get_productivity_patterns()
        
        # 时段分布
        hour_group = QtWidgets.QGroupBox("24小时生产力分布")
        hour_layout = QtWidgets.QVBoxLayout(hour_group)
        
        hour_chart = self.create_hour_distribution_chart(patterns['hourly_distribution'])
        hour_layout.addWidget(hour_chart)
        
        # 最高效时段
        productive_text = "最高效时段: "
        for hour, data in patterns['productive_hours'][:3]:
            productive_text += f"{hour}:00-{hour+1}:00 ({data['count']}个), "
        
        hour_summary = QtWidgets.QLabel(productive_text.rstrip(", "))
        hour_summary.setAlignment(QtCore.Qt.AlignCenter)
        hour_layout.addWidget(hour_summary)
        
        layout.addWidget(hour_group)
        
        # 星期分布
        weekday_group = QtWidgets.QGroupBox("星期分布")
        weekday_layout = QtWidgets.QVBoxLayout(weekday_group)
        
        weekday_chart = self.create_weekday_chart(patterns['weekday_distribution'])
        weekday_layout.addWidget(weekday_chart)
        
        layout.addWidget(weekday_group)
        
        self.tab_widget.addTab(widget, "🔍 模式分析")
    
    def create_tasks_tab(self):
        """创建任务分析选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        task_analysis = self.stats.get_task_analysis()
        
        # 任务统计摘要
        summary_group = QtWidgets.QGroupBox("任务统计摘要")
        summary_layout = QtWidgets.QFormLayout(summary_group)
        
        summary_layout.addRow("总任务数:", QtWidgets.QLabel(str(task_analysis['total_tasks'])))
        summary_layout.addRow("总时长:", QtWidgets.QLabel(f"{task_analysis['total_hours']:.1f} 小时"))
        
        if task_analysis['most_focused']:
            summary_layout.addRow("最专注任务:", 
                QtWidgets.QLabel(f"{task_analysis['most_focused']['name']} "
                               f"({task_analysis['most_focused']['avg_focus']:.1f}%)"))
        
        if task_analysis['most_time']:
            summary_layout.addRow("最耗时任务:", 
                QtWidgets.QLabel(f"{task_analysis['most_time']['name']} "
                               f"({task_analysis['most_time']['hours']:.1f}小时)"))
        
        layout.addWidget(summary_group)
        
        # 任务分布图
        if task_analysis['tasks']:
            task_chart = self.create_task_distribution_chart(task_analysis['tasks'])
            layout.addWidget(task_chart)
        
        # 任务列表
        task_table = self.create_task_table(task_analysis['tasks'])
        layout.addWidget(task_table)
        
        self.tab_widget.addTab(widget, "📋 任务分析")
    
    def create_stat_card(self, label: str, value: str, icon: str = "") -> QtWidgets.QWidget:
        """创建统计卡片"""
        card = QtWidgets.QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(card)
        
        # 图标和数值
        value_layout = QtWidgets.QHBoxLayout()
        
        if icon:
            icon_label = QtWidgets.QLabel(icon)
            icon_label.setStyleSheet("font-size: 24px;")
            value_layout.addWidget(icon_label)
        
        value_label = QtWidgets.QLabel(value)
        value_label.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: #2c3e50;
        """)
        value_layout.addWidget(value_label)
        value_layout.addStretch()
        
        layout.addLayout(value_layout)
        
        # 标签
        label_widget = QtWidgets.QLabel(label)
        label_widget.setStyleSheet("""
            font-size: 14px;
            color: #7f8c8d;
        """)
        layout.addWidget(label_widget)
        
        return card
    
    def create_week_chart(self, daily_distribution: List[Dict]) -> QChartView:
        """创建周统计图表"""
        # 创建柱状图
        series = QBarSeries()
        
        bar_set = QBarSet("番茄数")
        for day_data in daily_distribution:
            bar_set.append(day_data['pomodoros'])
        
        series.append(bar_set)
        
        # 创建图表
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("本周每日番茄数")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # 设置X轴
        categories = [d['day'] for d in daily_distribution]
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, QtCore.Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        # 设置Y轴
        axis_y = QValueAxis()
        axis_y.setRange(0, max([d['pomodoros'] for d in daily_distribution] + [1]) + 1)
        chart.addAxis(axis_y, QtCore.Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        # 创建视图
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QtGui.QPainter.Antialiasing)
        chart_view.setMinimumHeight(200)
        
        return chart_view
    
    def create_trend_chart(self, weekly_trend: List[Dict]) -> QChartView:
        """创建趋势图表"""
        # 创建折线图
        series = QLineSeries()
        
        for i, week_data in enumerate(weekly_trend):
            series.append(i, week_data['pomodoros'])
        
        # 创建图表
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("每周趋势")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # 设置坐标轴
        axis_x = QValueAxis()
        axis_x.setRange(0, len(weekly_trend) - 1)
        axis_x.setLabelFormat("%d")
        axis_x.setTitleText("周")
        
        axis_y = QValueAxis()
        max_value = max([w['pomodoros'] for w in weekly_trend] + [1])
        axis_y.setRange(0, max_value + 5)
        axis_y.setLabelFormat("%d")
        axis_y.setTitleText("番茄数")
        
        chart.addAxis(axis_x, QtCore.Qt.AlignBottom)
        chart.addAxis(axis_y, QtCore.Qt.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        
        # 创建视图
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QtGui.QPainter.Antialiasing)
        chart_view.setMinimumHeight(300)
        
        return chart_view
    
    def create_hour_distribution_chart(self, hourly_data: Dict) -> QChartView:
        """创建小时分布图表"""
        # 创建柱状图
        series = QBarSeries()
        
        # 按时段分组（早晨、上午、下午、晚上）
        morning = QBarSet("早晨(6-9)")
        forenoon = QBarSet("上午(9-12)")
        afternoon = QBarSet("下午(12-18)")
        evening = QBarSet("晚上(18-24)")
        night = QBarSet("深夜(0-6)")
        
        for hour in range(24):
            count = hourly_data[hour]['count']
            if 6 <= hour < 9:
                morning.append(count)
            elif 9 <= hour < 12:
                forenoon.append(count)
            elif 12 <= hour < 18:
                afternoon.append(count)
            elif 18 <= hour < 24:
                evening.append(count)
            else:
                night.append(count)
        
        # 只添加有数据的时段
        if morning.sum() > 0: series.append(morning)
        if forenoon.sum() > 0: series.append(forenoon)
        if afternoon.sum() > 0: series.append(afternoon)
        if evening.sum() > 0: series.append(evening)
        if night.sum() > 0: series.append(night)
        
        # 创建图表
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("时段生产力分布")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # 创建视图
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QtGui.QPainter.Antialiasing)
        chart_view.setMinimumHeight(250)
        
        return chart_view
    
    def create_weekday_chart(self, weekday_data: Dict) -> QChartView:
        """创建星期分布图表"""
        # 创建饼图
        series = QPieSeries()
        
        weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#DDA0DD', '#98D8C8']
        
        for i, day_name in enumerate(weekdays):
            count = weekday_data.get(i, 0)
            if count > 0:
                slice = series.append(f"{day_name} ({count})", count)
                slice.setBrush(QtGui.QColor(colors[i]))
                slice.setLabelVisible(True)
        
        # 创建图表
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("星期分布")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # 创建视图
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QtGui.QPainter.Antialiasing)
        chart_view.setMinimumHeight(250)
        
        return chart_view
    
    def create_task_distribution_chart(self, tasks: List[Dict]) -> QChartView:
        """创建任务分布图表"""
        # 创建饼图
        series = QPieSeries()
        
        # 只显示前5个任务，其他合并为"其他"
        top_tasks = tasks[:5]
        other_hours = sum(task['hours'] for task in tasks[5:])
        
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#DDA0DD']
        
        for i, task in enumerate(top_tasks):
            slice = series.append(
                f"{task['name'][:15]}... ({task['hours']:.1f}h)",
                task['hours']
            )
            slice.setBrush(QtGui.QColor(colors[i % len(colors)]))
            slice.setLabelVisible(True)
        
        if other_hours > 0:
            slice = series.append(f"其他 ({other_hours:.1f}h)", other_hours)
            slice.setBrush(QtGui.QColor('#95A5A6'))
            slice.setLabelVisible(True)
        
        # 创建图表
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("任务时间分布")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # 创建视图
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QtGui.QPainter.Antialiasing)
        chart_view.setMinimumHeight(300)
        
        return chart_view
    
    def create_task_table(self, tasks: List[Dict]) -> QtWidgets.QTableWidget:
        """创建任务表格"""
        table = QtWidgets.QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(['任务名称', '番茄数', '总时长', '平均专注度', '最后工作'])
        
        # 设置表格样式
        table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #007bff;
                color: white;
            }
        """)
        
        # 填充数据
        table.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(task['name']))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(task['sessions'])))
            table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{task['hours']:.1f} 小时"))
            table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{task['avg_focus']:.1f}%"))
            table.setItem(i, 4, QtWidgets.QTableWidgetItem(task['last_worked']))
        
        # 调整列宽
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()
        
        return table
