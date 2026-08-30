"""
Kioxus 简单示例

运行方式：
    python examples/simple_demo.py
"""

import sys
import os

# 将 src 目录加入路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from main import Kioxus


def main():
    # 初始化 Kioxus
    kioxus = Kioxus(base_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    kioxus.initialize()

    print("Kioxus 简单示例")
    print("输入 'quit' 退出\n")

    while True:
        user_input = input("你: ")
        if user_input.lower() in ('quit', 'exit', 'q'):
            break

        response = kioxus.chat(user_input)
        print(f"Kioxus: {response}\n")


if __name__ == "__main__":
    main()
