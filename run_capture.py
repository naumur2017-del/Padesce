import subprocess
import sys

with open('dump_out.txt', 'w', encoding='utf-8') as f:
    result = subprocess.run([sys.executable, 'manage.py', 'dumpdata', '--exclude', 'contenttypes', '--exclude', 'auth.Permission', '--output', 'all_data.json'], capture_output=True, text=True)
    f.write("STDOUT:\n" + result.stdout)
    f.write("\nSTDERR:\n" + result.stderr)
