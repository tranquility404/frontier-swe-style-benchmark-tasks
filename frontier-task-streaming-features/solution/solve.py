#!/usr/bin/env python3
import os, shutil, sys
from pathlib import Path
root=Path("/app"); shutil.copy2(Path(__file__).parent/"stream_engine.py",root/"stream_engine.py"); os.chmod(root/"stream_engine.py",0o755)
os.execv(sys.executable,[sys.executable,str(root/"stream_engine.py")])
