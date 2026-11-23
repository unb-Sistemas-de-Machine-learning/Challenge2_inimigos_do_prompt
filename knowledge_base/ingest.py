"""Script inicial de ingestão para a base de conhecimento do ErgoAI."""

from pathlib import Path

RAW_DIR = Path(__file__).parent / "raw"
PROCESSED_DIR = Path(__file__).parent / "processed"


def main() -> None:
    """Ponto de entrada do pipeline de ingestão (a implementar)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    files = [p for p in RAW_DIR.iterdir() if p.is_file() and p.name != ".gitkeep"]
    print(f"Encontrados {len(files)} arquivo(s) em {RAW_DIR}.")


if __name__ == "__main__":
    main()
