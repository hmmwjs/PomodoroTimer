#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键打包脚本：将番茄钟应用打包成独立可执行文件
"""

import os
import sys
import shutil
import platform
import subprocess
import time
from pathlib import Path

# 修复 Windows 控制台编码问题
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

class OneClickBuilder:
    def __init__(self):
        self.system = platform.system()
        self.app_dir = Path(__file__).parent
        self.build_dir = self.app_dir / "build"
        self.dist_dir = self.app_dir / "dist"
        self.app_name = "PomodoroTimer"
        self.version = "2.0"
    
    def run_command(self, command):
        print(f"运行命令: {command}")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True
        )
        stdout, stderr = process.communicate()
        return_code = process.returncode

        print(f"返回码: {return_code}")
        if stdout:
            print(f"输出: {stdout}")
        if stderr:
            print(f"错误: {stderr}")

        return stdout, stderr, return_code
    
    def check_dependencies(self):
        print("开始检查依赖...")
        required_packages = {
            "PyQt5": "PyQt5",
            "PyInstaller": "pyinstaller",
            "sqlite3": "sqlite3"
        }
        
        missing_packages = []
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list"],
            capture_output=True,
            text=True
        )
        installed_packages = result.stdout.lower()

        for display_name, package_name in required_packages.items():
            if package_name.lower() == "sqlite3":
                try:
                    import sqlite3
                    print(f"{display_name} 已安装")
                except ImportError:
                    missing_packages.append(package_name)
                    print(f"缺少依赖: {display_name}")
            elif package_name.lower() not in installed_packages:
                missing_packages.append(package_name)
                print(f"缺少依赖: {display_name}")
            else:
                print(f"{display_name} 已安装")

        if missing_packages:
            print("安装缺失的依赖...")
            for package in missing_packages:
                if package != "sqlite3":
                    self.run_command(f"{sys.executable} -m pip install {package}")

            for package in missing_packages:
                if package == "sqlite3":
                    try:
                        import sqlite3
                    except ImportError:
                        print(f"{package} 安装失败")
                        return False
                else:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "list"],
                        capture_output=True,
                        text=True
                    )
                    if package.lower() not in result.stdout.lower():
                        print(f"{package} 安装失败")
                        return False
        
        return True
    
    def clean_build_dirs(self):
        print("清理构建目录...")
        for dir_path in [self.build_dir, self.dist_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"已删除目录 {dir_path.name}/")
    
    def build_executable(self):
        print("开始构建可执行文件...")
        timer_py = self.app_dir / "timer.py"
        if not timer_py.exists():
            print(f"未找到主程序文件: {timer_py}")
            return None

        icon_file = self.app_dir / "timer.ico"
        sounds_dir = self.app_dir / "sounds"
        config_file = self.app_dir / "config.json"

        cmd = f"{sys.executable} -m PyInstaller --onefile --windowed --name={self.app_name}"
        if icon_file.exists():
            cmd += f" --icon=\"{icon_file}\""

        hidden_imports = [
            "PyQt5",
            "PyQt5.QtCore",
            "PyQt5.QtGui",
            "PyQt5.QtWidgets",
            "PyQt5.QtChart",
            "screeninfo",
            "sqlite3",
            "json",
            "csv"
        ]
        for imp in hidden_imports:
            cmd += f" --hidden-import={imp}"

        cmd += f" \"{timer_py}\""
        stdout, stderr, return_code = self.run_command(cmd)

        if return_code != 0:
            print("构建失败")
            return None

        exe_name = f"{self.app_name}.exe" if self.system == "Windows" else self.app_name
        exe_path = self.dist_dir / exe_name

        if exe_path.exists():
            print(f"可执行文件创建成功: {exe_path}")
            print(f"大小: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
            self.copy_required_files_to_dist(icon_file, sounds_dir, config_file)
            return exe_path
        else:
            print("未找到生成的可执行文件")
            return None

    def copy_required_files_to_dist(self, icon_file, sounds_dir, config_file):
        print("复制所需文件到 dist 目录...")
        if icon_file.exists():
            shutil.copy2(icon_file, self.dist_dir / icon_file.name)
            print(f"已复制 {icon_file.name}")
        if config_file.exists():
            shutil.copy2(config_file, self.dist_dir / config_file.name)
            print(f"已复制 {config_file.name}")
        if sounds_dir.exists():
            dest_sounds_dir = self.dist_dir / "sounds"
            if dest_sounds_dir.exists():
                shutil.rmtree(dest_sounds_dir)
            shutil.copytree(sounds_dir, dest_sounds_dir)
            print("已复制 sounds 文件夹")
        db_file = self.app_dir / "pomodoro_data.db"
        if db_file.exists():
            shutil.copy2(db_file, self.dist_dir / db_file.name)
            print(f"已复制 {db_file.name}")
    
    def test_executable(self):
        print("测试可执行文件...")
        exe_name = f"{self.app_name}.exe" if self.system == "Windows" else self.app_name
        exe_path = self.dist_dir / exe_name
        if not exe_path.exists():
            print("未找到可执行文件")
            return False
        print("测试运行中，5秒后自动终止...")
        try:
            process = subprocess.Popen([str(exe_path)])
            time.sleep(5)
            if process.poll() is None:
                print("可执行文件正常运行")
                process.terminate()
                return True
            else:
                print(f"程序崩溃，返回码: {process.returncode}")
                return False
        except Exception as e:
            print(f"测试出错: {e}")
            return False
    
    def run_build(self):
        print("开始构建番茄钟应用")
        if not self.check_dependencies():
            print("依赖检查失败，终止构建")
            return False

        self.clean_build_dirs()
        exe_path = self.build_executable()
        if not exe_path:
            print("构建失败")
            return False

        if self.test_executable():
            print("构建完成")
            print(f"可执行文件路径: {exe_path}")
        else:
            print("构建完成，但测试失败")

        return True


def main():
    try:
        builder = OneClickBuilder()
        builder.run_build()
    except KeyboardInterrupt:
        print("构建被用户中断")
    except Exception as e:
        print(f"构建出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
