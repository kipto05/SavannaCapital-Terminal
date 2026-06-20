from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError
import sys

env = Environment(loader=FileSystemLoader("dashboard/templates"))
try:
    template = env.get_template("v3/pages/trade_operations.html")
    print("Jinja2 syntax OK")
except TemplateSyntaxError as e:
    print(f"FAIL: {e}")
    sys.exit(1)
