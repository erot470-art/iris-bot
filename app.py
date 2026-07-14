import sys
from pathlib import Path

# Добавляем корневую папку в путь
sys.path.insert(0, str(Path(__file__).parent))

from bot.main import main

if __name__ == "__main__":
    main()
