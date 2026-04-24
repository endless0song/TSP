# run.py
# !/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "subway_traversal.settings")

    from django.core.management import execute_from_command_line

    print("=" * 60)
    print("🚇 合肥地铁全站点遍历系统")
    print("=" * 60)
    print("\n服务器启动中...")
    print("请访问: http://127.0.0.1:8000")
    print("按 Ctrl+C 停止服务器\n")

    execute_from_command_line([sys.argv[0], "runserver", "127.0.0.1:8000"])