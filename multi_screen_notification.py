#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多屏通知模块
支持在多个显示器上显示通知
"""

import sys
import threading
from typing import List, Optional, Callable
from PyQt5 import QtWidgets, QtCore, QtGui

try:
    from screeninfo import get_monitors
except ImportError:
    # 如果没有安装screeninfo，提供一个后备方案
    def get_monitors():
        """获取屏幕信息的后备方案"""
        desktop = QtWidgets.QApplication.desktop()
        monitors = []
        for i in range(desktop.screenCount()):
            rect = desktop.screenGeometry(i)
            class Monitor:
                def __init__(self, x, y, width, height):
                    self.x = x
                    self.y = y
                    self.width = width
                    self.height = height
            monitors.append(Monitor(rect.x(), rect.y(), rect.width(), rect.height()))
        return monitors


class NotificationWindow(QtWidgets.QWidget):
    """通知窗口"""
    
    clicked = QtCore.pyqtSignal()
    
    def __init__(self, title: str, message: str, duration: int = 3000,
                 bg_color: str = "#2c2c2c", fg_color: str = "#ffffff",
                 parent=None):
        super().__init__(parent)
        
        self.duration = duration
        self.opacity = 0.0
        self.fade_in_timer = None
        self.fade_out_timer = None
        
        # 设置窗口属性
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool |
            QtCore.Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        
        # 创建UI
        self.setup_ui(title, message, bg_color, fg_color)
        
        # 启动动画
        self.fade_in()
    
    def setup_ui(self, title: str, message: str, bg_color: str, fg_color: str):
        """设置UI"""
        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 内容容器
        self.content_widget = QtWidgets.QWidget()
        self.content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
        """)
        
        content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(20, 15, 20, 15)
        content_layout.setSpacing(5)
        
        # 标题
        if title:
            title_label = QtWidgets.QLabel(title)
            title_label.setStyleSheet(f"""
                color: {fg_color};
                font-size: 16px;
                font-weight: bold;
            """)
            content_layout.addWidget(title_label)
        
        # 消息
        if message:
            message_label = QtWidgets.QLabel(message)
            message_label.setWordWrap(True)
            message_label.setStyleSheet(f"""
                color: {fg_color};
                font-size: 14px;
                opacity: 0.9;
            """)
            content_layout.addWidget(message_label)
        
        # 添加阴影效果
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        shadow.setOffset(0, 5)
        self.content_widget.setGraphicsEffect(shadow)
        
        main_layout.addWidget(self.content_widget)
    
    def fade_in(self):
        """淡入动画"""
        self.fade_in_timer = QtCore.QTimer()
        self.fade_in_timer.timeout.connect(self._fade_in_step)
        self.fade_in_timer.start(20)  # 50fps
    
    def _fade_in_step(self):
        """淡入步骤"""
        self.opacity += 0.05
        if self.opacity >= 0.95:
            self.opacity = 0.95
            self.fade_in_timer.stop()
            
            # 设置自动关闭定时器
            QtCore.QTimer.singleShot(self.duration, self.fade_out)
        
        self.setWindowOpacity(self.opacity)
    
    def fade_out(self):
        """淡出动画"""
        if self.fade_out_timer:
            return  # 已经在淡出
            
        self.fade_out_timer = QtCore.QTimer()
        self.fade_out_timer.timeout.connect(self._fade_out_step)
        self.fade_out_timer.start(20)  # 50fps
    
    def _fade_out_step(self):
        """淡出步骤"""
        self.opacity -= 0.05
        if self.opacity <= 0:
            self.opacity = 0
            self.fade_out_timer.stop()
            self.close()
        
        self.setWindowOpacity(self.opacity)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
            self.fade_out()
    
    def enterEvent(self, event):
        """鼠标进入事件"""
        # 停止淡出
        if self.fade_out_timer:
            self.fade_out_timer.stop()
            self.fade_out_timer = None
        
        # 恢复完全不透明
        self.opacity = 0.95
        self.setWindowOpacity(self.opacity)
    
    def leaveEvent(self, event):
        """鼠标离开事件"""
        # 重新开始计时
        QtCore.QTimer.singleShot(1000, self.fade_out)


class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.notifications: List[NotificationWindow] = []
    
    def show_notification(self, title: str, message: str, 
                         duration: int = 3000,
                         screen_index: Optional[int] = None,
                         position: str = "bottom-right",
                         bg_color: str = "#2c2c2c",
                         fg_color: str = "#ffffff",
                         on_click: Optional[Callable] = None) -> NotificationWindow:
        """显示通知
        
        Args:
            title: 标题
            message: 消息内容
            duration: 持续时间（毫秒）
            screen_index: 屏幕索引，None表示所有屏幕
            position: 位置 (top-left, top-right, bottom-left, bottom-right)
            bg_color: 背景颜色
            fg_color: 前景颜色
            on_click: 点击回调函数
        """
        # 创建通知窗口
        notification = NotificationWindow(title, message, duration, bg_color, fg_color)
        
        if on_click:
            notification.clicked.connect(on_click)
        
        # 计算位置
        monitors = get_monitors()
        
        if screen_index is not None and 0 <= screen_index < len(monitors):
            # 指定屏幕
            monitors = [monitors[screen_index]]
        
        # 在每个屏幕上显示
        for monitor in monitors:
            self._position_notification(notification, monitor, position)
            notification.show()
            break  # 只在第一个屏幕显示（如果需要多屏，需要创建多个窗口）
        
        # 管理通知列表
        self.notifications.append(notification)
        # 修复 lambda 函数问题
        current_notification = notification
        notification.destroyed.connect(lambda: self.notifications.remove(current_notification) if current_notification in self.notifications else None)
        
        return notification
    
    def _position_notification(self, notification: NotificationWindow, 
                             monitor, position: str):
        """定位通知窗口"""
        # 获取通知窗口大小
        notification.adjustSize()
        width = notification.width()
        height = notification.height()
        
        # 边距
        margin = 20
        
        # 计算位置
        if "right" in position:
            x = monitor.x + monitor.width - width - margin
        else:
            x = monitor.x + margin
        
        if "bottom" in position:
            y = monitor.y + monitor.height - height - margin - 40  # 留出任务栏空间
        else:
            y = monitor.y + margin
        
        notification.move(x, y)
    
    def show_multi_screen_notification(self, title: str, message: str,
                                     duration: int = 3000,
                                     position: str = "bottom-right",
                                     bg_color: str = "#2c2c2c",
                                     fg_color: str = "#ffffff",
                                     on_click: Optional[Callable] = None):
        """在所有屏幕上显示通知"""
        monitors = get_monitors()
        notifications = []
        
        for i, monitor in enumerate(monitors):
            notification = NotificationWindow(title, message, duration, bg_color, fg_color)
            
            if on_click:
                notification.clicked.connect(on_click)
            
            self._position_notification(notification, monitor, position)
            notification.show()
            
            notifications.append(notification)
            self.notifications.append(notification)
            # 修复 lambda 函数问题，使用局部变量存储当前通知
            current_notification = notification
            notification.destroyed.connect(lambda: self.notifications.remove(current_notification) if current_notification in self.notifications else None)
        
        return notifications
    
    def close_all(self):
        """关闭所有通知"""
        for notification in self.notifications[:]:
            try:
                notification.close()
            except:
                pass
        self.notifications.clear()


# 全局通知管理器实例
_notification_manager = None


def get_notification_manager() -> NotificationManager:
    """获取全局通知管理器"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def show_notification(title: str, message: str, duration: int = 3000,
                     screen_index: Optional[int] = None,
                     position: str = "bottom-right",
                     bg_color: str = "#2c2c2c",
                     fg_color: str = "#ffffff",
                     on_click: Optional[Callable] = None) -> NotificationWindow:
    """显示通知的便捷函数"""
    manager = get_notification_manager()
    return manager.show_notification(
        title, message, duration, screen_index, 
        position, bg_color, fg_color, on_click
    )


def multi_screen_notification(title: str, message: str, duration: int = 3,
                            bg_color: str = "#2c2c2c", 
                            fg_color: str = "#ffffff",
                            on_click: Optional[Callable] = None):
    """在所有屏幕上显示通知的便捷函数
    
    Args:
        title: 标题
        message: 消息内容
        duration: 持续时间（秒）
        bg_color: 背景颜色
        fg_color: 前景颜色
        on_click: 点击回调函数
    """
    manager = get_notification_manager()
    return manager.show_multi_screen_notification(
        title, message, duration * 1000, "bottom-right",
        bg_color, fg_color, on_click
    )


def close_all_notifications():
    """关闭所有通知"""
    manager = get_notification_manager()
    manager.close_all()


# 测试代码
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    
    # 测试单屏通知
    def on_notification_click():
        print("通知被点击了！")
    
    # 显示通知
    show_notification(
        "🍅 番茄钟",
        "这是一个测试通知，点击关闭",
        duration=5000,
        on_click=on_notification_click
    )
    
    # 3秒后显示多屏通知
    QtCore.QTimer.singleShot(3000, lambda: multi_screen_notification(
        "⏰ 时间到！",
        "休息一下吧",
        duration=5,
        bg_color="#4ECDC4",
        fg_color="#FFFFFF"
    ))
    
    sys.exit(app.exec_())
