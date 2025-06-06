#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库管理模块
处理所有数据持久化操作
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import os


@dataclass
class PomodoroSession:
    """番茄钟会话数据类"""
    start_time: datetime
    end_time: datetime
    duration: int  # 秒
    task_name: str
    completed: bool
    interruptions: int
    focus_score: float
    id: Optional[int] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


@dataclass
class DailyStat:
    """每日统计数据类"""
    date: date
    total_pomodoros: int
    total_minutes: int
    avg_focus_score: float
    completed_tasks: int
    most_productive_hour: Optional[int] = None
    streak_days: int = 0


@dataclass
class Achievement:
    """成就数据类"""
    id: str
    name: str
    description: str
    icon: str
    unlocked: bool
    unlocked_date: Optional[datetime] = None
    progress: float = 0.0
    max_progress: float = 1.0
    category: str = "general"
    rarity: str = "common"  # common, rare, epic, legendary


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "pomodoro_data.db"):
        self.db_path = db_path
        self.connection = None
        self.init_database()
    
    def init_database(self):
        """初始化数据库表"""
        try:
            # 设置超时参数，避免锁定问题
            self.connection = sqlite3.connect(self.db_path, timeout=20)
            
            # 启用外键约束
            self.connection.execute("PRAGMA foreign_keys = ON")
            
            # 配置连接，提高并发性能
            self.connection.execute("PRAGMA journal_mode = WAL")
            self.connection.execute("PRAGMA synchronous = NORMAL")
            
            cursor = self.connection.cursor()
            
            # 创建会话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    duration INTEGER NOT NULL,
                    task_name TEXT NOT NULL,
                    completed BOOLEAN NOT NULL,
                    interruptions INTEGER DEFAULT 0,
                    focus_score REAL DEFAULT 100,
                    tags TEXT,
                    notes TEXT
                )
            """)
            
            # 创建每日统计表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date DATE PRIMARY KEY,
                    total_pomodoros INTEGER DEFAULT 0,
                    total_minutes INTEGER DEFAULT 0,
                    avg_focus_score REAL DEFAULT 0,
                    completed_tasks INTEGER DEFAULT 0,
                    most_productive_hour INTEGER,
                    streak_days INTEGER DEFAULT 0
                )
            """)
            
            # 创建成就表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    icon TEXT NOT NULL,
                    unlocked BOOLEAN DEFAULT FALSE,
                    unlocked_date TIMESTAMP,
                    progress REAL DEFAULT 0,
                    max_progress REAL DEFAULT 1,
                    category TEXT DEFAULT 'general',
                    rarity TEXT DEFAULT 'common'
                )
            """)
            
            # 创建用户统计表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_stats (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_date 
                ON sessions(date(start_time))
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_task 
                ON sessions(task_name)
            """)
            
            self.connection.commit()
            
            # 初始化成就
            self._init_achievements()
            
        except Exception as e:
            print(f"初始化数据库失败: {e}")
            # 尝试关闭连接并重新连接
            try:
                if self.connection:
                    self.connection.close()
                self.connection = sqlite3.connect(self.db_path, timeout=30)
            except:
                pass
    
    def _init_achievements(self):
        """初始化成就列表"""
        achievements = [
            # 基础成就
            Achievement("first_pomodoro", "初学者", "完成第一个番茄钟", "🌱", False, max_progress=1),
            Achievement("ten_pomodoros", "进阶者", "完成10个番茄钟", "🌿", False, max_progress=10),
            Achievement("hundred_pomodoros", "专注达人", "完成100个番茄钟", "🌳", False, max_progress=100, rarity="rare"),
            Achievement("thousand_pomodoros", "专注大师", "完成1000个番茄钟", "🌲", False, max_progress=1000, rarity="epic"),
            
            # 连续成就
            Achievement("three_day_streak", "三日坚持", "连续3天完成番茄钟", "🔥", False, max_progress=3),
            Achievement("week_streak", "周度达人", "连续7天完成番茄钟", "💪", False, max_progress=7, rarity="rare"),
            Achievement("month_streak", "月度英雄", "连续30天完成番茄钟", "🏆", False, max_progress=30, rarity="epic"),
            Achievement("year_streak", "年度传奇", "连续365天完成番茄钟", "👑", False, max_progress=365, rarity="legendary"),
            
            # 每日成就
            Achievement("daily_goal", "日积月累", "完成每日目标", "☀️", False),
            Achievement("early_bird", "早起鸟", "早上6点前开始第一个番茄", "🐦", False),
            Achievement("night_owl", "夜猫子", "晚上10点后完成番茄", "🦉", False),
            Achievement("perfect_day", "完美一天", "一天内完成8个番茄钟", "⭐", False, max_progress=8),
            
            # 专注成就
            Achievement("perfect_focus", "完美专注", "完成一个无中断的番茄钟", "🎯", False),
            Achievement("focus_master", "专注大师", "连续5个番茄钟无中断", "🧘", False, max_progress=5, rarity="rare"),
            Achievement("deep_work", "深度工作", "单个任务完成10个番茄钟", "🌊", False, max_progress=10, rarity="rare"),
            
            # 特殊成就
            Achievement("weekend_warrior", "周末战士", "周末完成10个番茄钟", "⚔️", False, max_progress=10),
            Achievement("task_crusher", "任务粉碎机", "一天完成10个不同任务", "💥", False, max_progress=10, rarity="rare"),
            Achievement("marathon", "马拉松", "累计工作100小时", "🏃", False, max_progress=6000, rarity="epic"),
            
            # 里程碑成就
            Achievement("time_traveler", "时间旅行者", "累计专注1000小时", "⏰", False, max_progress=60000, rarity="legendary"),
            Achievement("task_master", "任务大师", "完成1000个任务", "📋", False, max_progress=1000, rarity="legendary"),
        ]
        
        cursor = self.connection.cursor()
        
        for achievement in achievements:
            cursor.execute("""
                INSERT OR IGNORE INTO achievements 
                (id, name, description, icon, unlocked, progress, max_progress, category, rarity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                achievement.id, achievement.name, achievement.description,
                achievement.icon, achievement.unlocked, achievement.progress,
                achievement.max_progress, achievement.category, achievement.rarity
            ))
        
        self.connection.commit()
    
    def save_session(self, session: PomodoroSession) -> int:
        """保存番茄钟会话"""
        session_id = None
        try:
            cursor = self.connection.cursor()
            
            # 开始事务
            self.connection.execute("BEGIN TRANSACTION")
            
            tags_json = json.dumps(session.tags) if session.tags else None
            
            cursor.execute("""
                INSERT INTO sessions 
                (start_time, end_time, duration, task_name, completed, 
                 interruptions, focus_score, tags, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.start_time, session.end_time, session.duration,
                session.task_name, session.completed, session.interruptions,
                session.focus_score, tags_json, session.notes
            ))
            
            session_id = cursor.lastrowid
            
            # 提交事务
            self.connection.commit()
            
            # 更新每日统计和用户统计
            try:
                self._update_daily_stats(session.start_time.date())
                self._update_user_stats()
            except Exception as e:
                print(f"更新统计数据时发生错误: {e}")
                # 这里不回滚，因为会话已经保存成功
            
            return session_id
            
        except Exception as e:
            print(f"保存会话失败: {e}")
            # 回滚事务
            try:
                self.connection.rollback()
            except:
                pass
            
            # 尝试重新连接数据库
            try:
                self.connection.close()
                self.connection = sqlite3.connect(self.db_path, timeout=20)
            except:
                pass
            
            return -1
    
    def get_sessions(self, start_date: Optional[date] = None, 
                    end_date: Optional[date] = None,
                    task_name: Optional[str] = None) -> List[PomodoroSession]:
        """获取会话记录"""
        sessions = []
        try:
            cursor = self.connection.cursor()
            
            query = "SELECT * FROM sessions WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND date(start_time) >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND date(start_time) <= ?"
                params.append(end_date)
            
            if task_name:
                query += " AND task_name LIKE ?"
                params.append(f"%{task_name}%")
            
            query += " ORDER BY start_time DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            for row in rows:
                tags = json.loads(row[8]) if row[8] else None
                session = PomodoroSession(
                    id=row[0],
                    start_time=datetime.fromisoformat(row[1]),
                    end_time=datetime.fromisoformat(row[2]),
                    duration=row[3],
                    task_name=row[4],
                    completed=bool(row[5]),
                    interruptions=row[6],
                    focus_score=row[7],
                    tags=tags,
                    notes=row[9]
                )
                sessions.append(session)
                
        except Exception as e:
            print(f"获取会话记录时发生错误: {e}")
            
        return sessions
    
    def get_daily_stats(self, date: date) -> Optional[DailyStat]:
        """获取每日统计"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                SELECT * FROM daily_stats WHERE date = ?
            """, (date,))
            
            row = cursor.fetchone()
            
            if row:
                return DailyStat(
                    date=date,
                    total_pomodoros=row[1],
                    total_minutes=row[2],
                    avg_focus_score=row[3],
                    completed_tasks=row[4],
                    most_productive_hour=row[5],
                    streak_days=row[6]
                )
            
        except Exception as e:
            print(f"获取每日统计时发生错误: {e}")
            
        return None
    
    def get_stats_range(self, start_date: date, end_date: date) -> List[DailyStat]:
        """获取日期范围内的统计"""
        stats = []
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                SELECT * FROM daily_stats 
                WHERE date >= ? AND date <= ?
                ORDER BY date
            """, (start_date, end_date))
            
            for row in cursor.fetchall():
                stat = DailyStat(
                    date=datetime.strptime(row[0], '%Y-%m-%d').date(),
                    total_pomodoros=row[1],
                    total_minutes=row[2],
                    avg_focus_score=row[3],
                    completed_tasks=row[4],
                    most_productive_hour=row[5],
                    streak_days=row[6]
                )
                stats.append(stat)
                
        except Exception as e:
            print(f"获取日期范围统计时发生错误: {e}")
            
        return stats
    
    def _update_daily_stats(self, date: date):
        """更新每日统计"""
        try:
            cursor = self.connection.cursor()
            
            # 计算当日统计
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_pomodoros,
                    SUM(duration) / 60 as total_minutes,
                    AVG(focus_score) as avg_focus_score,
                    COUNT(DISTINCT task_name) as completed_tasks,
                    strftime('%H', start_time) as hour
                FROM sessions
                WHERE date(start_time) = ? AND completed = 1
                GROUP BY strftime('%H', start_time)
                ORDER BY COUNT(*) DESC
                LIMIT 1
            """, (date,))
            
            result = cursor.fetchone()
            
            if result and result[0] > 0:
                # 计算连续天数
                streak = self._calculate_streak(date)
                
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO daily_stats
                        (date, total_pomodoros, total_minutes, avg_focus_score, 
                         completed_tasks, most_productive_hour, streak_days)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        date, result[0], result[1] or 0, result[2] or 0,
                        result[3] or 0, int(result[4]) if result[4] else None, streak
                    ))
                    self.connection.commit()
                except Exception as e:
                    print(f"更新每日统计失败: {e}")
                    self.connection.rollback()
        except Exception as e:
            print(f"更新每日统计时发生错误: {e}")
            # 如果出错，尝试重新连接数据库
            try:
                self.connection.close()
                self.connection = sqlite3.connect(self.db_path, timeout=20)
            except:
                pass
    
    def _calculate_streak(self, current_date: date) -> int:
        """计算连续天数"""
        try:
            cursor = self.connection.cursor()
            
            streak = 0
            check_date = current_date
            
            while True:
                cursor.execute("""
                    SELECT COUNT(*) FROM sessions
                    WHERE date(start_time) = ? AND completed = 1
                """, (check_date,))
                
                count = cursor.fetchone()[0]
                
                if count > 0:
                    streak += 1
                    check_date = check_date - timedelta(days=1)
                else:
                    break
            
            return streak
        except Exception as e:
            print(f"计算连续天数时发生错误: {e}")
            return 0
    
    def _update_user_stats(self):
        """更新用户总体统计"""
        try:
            cursor = self.connection.cursor()
            
            # 开始事务
            self.connection.execute("BEGIN TRANSACTION")
            
            # 总番茄数
            cursor.execute("""
                SELECT COUNT(*) FROM sessions WHERE completed = 1
            """)
            total_pomodoros = cursor.fetchone()[0]
            
            # 总时长（小时）
            cursor.execute("""
                SELECT SUM(duration) / 3600.0 FROM sessions WHERE completed = 1
            """)
            total_hours = cursor.fetchone()[0] or 0
            
            # 总任务数
            cursor.execute("""
                SELECT COUNT(DISTINCT task_name) FROM sessions
            """)
            total_tasks = cursor.fetchone()[0]
            
            # 平均专注度
            cursor.execute("""
                SELECT AVG(focus_score) FROM sessions WHERE completed = 1
            """)
            avg_focus = cursor.fetchone()[0] or 0
            
            # 最高连续天数
            cursor.execute("""
                SELECT MAX(streak_days) FROM daily_stats
            """)
            max_streak = cursor.fetchone()[0] or 0
            
            # 更新统计
            stats = {
                'total_pomodoros': str(total_pomodoros),
                'total_hours': f"{total_hours:.1f}",
                'total_tasks': str(total_tasks),
                'avg_focus': f"{avg_focus:.1f}",
                'max_streak': str(max_streak),
                'last_updated': datetime.now().isoformat()
            }
            
            for key, value in stats.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO user_stats (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, value))
            
            # 提交事务
            self.connection.commit()
            
        except Exception as e:
            print(f"更新用户统计时发生错误: {e}")
            # 回滚事务
            try:
                self.connection.rollback()
            except:
                pass
    
    def get_user_stats(self) -> Dict[str, Any]:
        """获取用户统计"""
        stats = {}
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("SELECT key, value FROM user_stats")
            rows = cursor.fetchall()
            
            for key, value in rows:
                # 尝试转换为数字
                try:
                    if '.' in value:
                        stats[key] = float(value)
                    else:
                        stats[key] = int(value)
                except ValueError:
                    stats[key] = value
            
        except Exception as e:
            print(f"获取用户统计时发生错误: {e}")
            
        return stats
    
    def get_achievements(self) -> List[Achievement]:
        """获取所有成就"""
        achievements = []
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM achievements ORDER BY unlocked DESC, rarity")
            
            for row in cursor.fetchall():
                achievement = Achievement(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    icon=row[3],
                    unlocked=bool(row[4]),
                    unlocked_date=datetime.fromisoformat(row[5]) if row[5] else None,
                    progress=row[6],
                    max_progress=row[7],
                    category=row[8],
                    rarity=row[9]
                )
                achievements.append(achievement)
                
        except Exception as e:
            print(f"获取成就列表时发生错误: {e}")
            
        return achievements
    
    def update_achievement(self, achievement_id: str, progress: float = None, 
                          unlocked: bool = None) -> bool:
        """更新成就进度"""
        try:
            cursor = self.connection.cursor()
            
            updates = []
            params = []
            
            if progress is not None:
                updates.append("progress = ?")
                params.append(progress)
            
            if unlocked is not None:
                updates.append("unlocked = ?")
                params.append(unlocked)
                
                if unlocked:
                    updates.append("unlocked_date = ?")
                    params.append(datetime.now())
            
            if updates:
                params.append(achievement_id)
                cursor.execute(f"""
                    UPDATE achievements 
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, params)
                
                self.connection.commit()
                return cursor.rowcount > 0
            
            return False
        except Exception as e:
            print(f"更新成就进度时发生错误: {e}")
            try:
                self.connection.rollback()
            except:
                pass
            return False
    
    def get_task_stats(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取任务统计（前N个最常见任务）"""
        tasks = []
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                SELECT 
                    task_name,
                    COUNT(*) as session_count,
                    SUM(duration) / 3600.0 as total_hours,
                    AVG(focus_score) as avg_focus,
                    MAX(date(start_time)) as last_worked
                FROM sessions
                WHERE completed = 1
                GROUP BY task_name
                ORDER BY session_count DESC
                LIMIT ?
            """, (limit,))
            
            for row in cursor.fetchall():
                tasks.append({
                    'name': row[0],
                    'sessions': row[1],
                    'hours': round(row[2], 1),
                    'avg_focus': round(row[3], 1),
                    'last_worked': row[4]
                })
                
        except Exception as e:
            print(f"获取任务统计时发生错误: {e}")
            
        return tasks
    
    def export_data(self, filepath: str, format: str = 'csv'):
        """导出数据"""
        import csv
        
        sessions = self.get_sessions()
        
        if format == 'csv':
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 写入标题
                writer.writerow([
                    'ID', '开始时间', '结束时间', '时长(分钟)', '任务名称',
                    '是否完成', '中断次数', '专注度', '标签', '备注'
                ])
                
                # 写入数据
                for session in sessions:
                    writer.writerow([
                        session.id,
                        session.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        session.end_time.strftime('%Y-%m-%d %H:%M:%S'),
                        session.duration // 60,
                        session.task_name,
                        '是' if session.completed else '否',
                        session.interruptions,
                        session.focus_score,
                        ','.join(session.tags) if session.tags else '',
                        session.notes or ''
                    ])
        
        elif format == 'json':
            with open(filepath, 'w', encoding='utf-8') as f:
                data = []
                for session in sessions:
                    session_dict = asdict(session)
                    session_dict['start_time'] = session.start_time.isoformat()
                    session_dict['end_time'] = session.end_time.isoformat()
                    data.append(session_dict)
                
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    def clear_all_data(self):
        """清空所有数据（危险操作）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 清空所有表
            cursor.execute("DELETE FROM sessions")
            cursor.execute("DELETE FROM daily_stats")
            cursor.execute("DELETE FROM user_stats")
            
            # 重置成就进度
            cursor.execute("""
                UPDATE achievements 
                SET unlocked = 0, unlocked_date = NULL, progress = 0
            """)
            
            conn.commit()
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
            except:
                pass
