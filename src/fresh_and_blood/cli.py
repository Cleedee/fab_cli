"""CLI mínima — placeholder até a Fase 1."""

from __future__ import annotations

import sys

from fresh_and_blood import __version__


def main() -> int:
    print(f"fresh-and-blood v{__version__} — assistente de decisão para FaB Silver Age")
    print("(em construção: motor de matemática chega na Fase 1)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
