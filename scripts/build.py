"""
Kioxus — 打包脚本

用法：
    python build.py              # 打包成单个exe
    python build.py --onefile     # 单文件模式（启动慢但单文件）
    python build.py --clean       # 清理构建目录
"""

import subprocess
import sys
import os
import shutil
import argparse

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")


def clean():
    """清理构建产物"""
    for d in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"已清理: {d}")
    for f in ["kioxus.spec"]:
        p = os.path.join(BASE_DIR, f)
        if os.path.exists(p):
            os.remove(p)
            print(f"已清理: {p}")


def build(onefile=False):
    """打包"""
    # 确保pyinstaller已安装
    try:
        import PyInstaller
    except ImportError:
        print("正在安装 PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 确保pywebview已安装
    try:
        import webview
    except ImportError:
        print("正在安装 pywebview...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview"])

    # 收集需要打包的文件
    datas = []

    # config目录
    config_dir = os.path.join(BASE_DIR, "config")
    if os.path.exists(config_dir):
        datas.append((config_dir, "config"))

    # .env文件
    env_file = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file):
        datas.append((env_file, "."))

    # data目录（如果存在）
    data_dir = os.path.join(BASE_DIR, "data")
    if os.path.exists(data_dir):
        datas.append((data_dir, "data"))

    # memory目录（如果存在）
    memory_dir = os.path.join(BASE_DIR, "memory")
    if os.path.exists(memory_dir):
        datas.append((memory_dir, "memory"))

    # 需要导入的隐藏模块
    hidden_imports = [
        "core",
        "core.engine",
        "core.input",
        "core.llm",
        "core.context",
        "core.output",
        "core.session",
        "core.memory_bridge",
        "core.reasoning",
        "core.planner",
        "core.tools",
        "core.builtin_tools",
        "core.decomposer",
        "core.verifier",
        "memory",
        "memory.memory",
        "memory.router",
        "memory.search",
        "memory.tags",
        "memory.compressor",
        "memory.janitor",
        "flask",
        "flask.json",
        "werkzeug",
        "webview",
    ]

    # PyInstaller参数
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "Kioxus",
        "--windowed",              # 无控制台窗口
        "--clean",
        "--noconfirm",
    ]

    # 设置图标
    icon_file = os.path.join(BASE_DIR, "logo.ico")
    if os.path.exists(icon_file):
        cmd.extend(["--icon", icon_file])

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # 添加数据文件
    for src, dst in datas:
        cmd.extend(["--add-data", f"{src};{dst}"])

    # 添加隐藏模块
    for mod in hidden_imports:
        cmd.extend(["--hidden-import", mod])

    # 入口文件
    cmd.append(os.path.join(BASE_DIR, "desktop.py"))

    print("=" * 50)
    print("  Kioxus 打包")
    print("=" * 50)
    print(f"模式: {'单文件' if onefile else '目录'}")
    print(f"命令: {' '.join(cmd)}")
    print()

    # 执行打包
    result = subprocess.run(cmd, cwd=BASE_DIR)

    if result.returncode == 0:
        print()
        print("=" * 50)
        print("  打包成功!")
        print("=" * 50)
        if onefile:
            exe_path = os.path.join(DIST_DIR, "Kioxus.exe")
            print(f"输出: {exe_path}")
            if os.path.exists(exe_path):
                size_mb = os.path.getsize(exe_path) / (1024 * 1024)
                print(f"大小: {size_mb:.1f} MB")
        else:
            exe_path = os.path.join(DIST_DIR, "Kioxus", "Kioxus.exe")
            print(f"输出目录: {os.path.join(DIST_DIR, 'Kioxus')}")
            print(f"入口: {exe_path}")
        print()
        print("运行: 双击 Kioxus.exe")
    else:
        print("\n打包失败，请检查错误信息")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Kioxus打包脚本")
    parser.add_argument("--onefile", action="store_true", help="单文件模式")
    parser.add_argument("--clean", action="store_true", help="清理构建目录")
    args = parser.parse_args()

    if args.clean:
        clean()
        return

    build(onefile=args.onefile)


if __name__ == "__main__":
    main()
