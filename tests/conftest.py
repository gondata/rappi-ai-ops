import sys
from pathlib import Path

# Agrega la raíz del proyecto al path para que pytest encuentre los módulos
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))