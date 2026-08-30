"""pytest conftest — 将 src/ 加入 sys.path"""
import sys
import os

src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
