"""
Kioxus 快速体验 Demo

运行前：
1. pip install -r requirements.txt
2. cp config/config.example.yaml config/config.yaml（填入你的API Key）
3. 在 .env 中填入 API Key

运行：
    python examples/simple_demo.py
"""

import sys
import os

# 将 src 目录加入路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

from main import Kioxus


def main():
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    kioxus = Kioxus(base_dir=base_dir)
    kioxus.initialize()

    print("=" * 40)
    print("  Kioxus 快速体验")
    print("=" * 40)
    print()
    print("这是一个完整的Agent演示：")
    print("  - 对话（有记忆）")
    print("  - 工具调用（代码执行）")
    print("  - 自我校验")
    print()
    print("输入 'quit' 退出")
    print()

    while True:
        user_input = input("你: ")
        if user_input.lower() in ('quit', 'exit', 'q'):
            break

        response = kioxus.chat(user_input)
        print(f"Kioxus: {response}")
        print()


if __name__ == "__main__":
    main()