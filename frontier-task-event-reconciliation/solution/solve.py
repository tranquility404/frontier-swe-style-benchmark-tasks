#!/usr/bin/env python3
import os, shutil, sys
from pathlib import Path

root = Path("/app")
src = Path(__file__).parent / "reconcile.py"
shutil.copy2(src, root / "reconcile.py")
os.chmod(root / "reconcile.py", 0o755)
os.execv(sys.executable, [sys.executable, str(root / "reconcile.py")])
