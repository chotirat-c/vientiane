"""Build the approved Morning Jade edition for Laos or Thailand."""
import argparse
from pathlib import Path
import runpy
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--country", choices=["laos", "thailand"], required=True)
parser.add_argument("--stage", choices=["proof", "final"], default="proof")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
builder = Path(__file__).resolve().parents[1] / "thailand_terrain/build_thailand_blue_150m.py"
sys.argv = [str(builder), "--morning-jade"]
if args.country == "laos":
    sys.argv.append("--laos")
if args.stage == "final":
    sys.argv.append("--final")
runpy.run_path(str(builder), run_name="__main__")
