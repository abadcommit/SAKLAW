"""Clear generated files from the model output directory."""

import shutil
from pathlib import Path

import backend.model.config as cfg


def clear_outputs():
    output_dir = Path(cfg.OUTPUT_DIR)

    if not output_dir.exists():
        print(f"Output directory does not exist: {output_dir}")
        return

    for item in output_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    print(f"Cleared output directory: {output_dir}")


if __name__ == "__main__":
    confirm = input("Clear ALL files in the model output directory? (y/N): ")

    if confirm.lower() == "y":
        clear_outputs()
    else:
        print("Cancelled.")