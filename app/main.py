if __package__:
    from .real_ui import main
else:
    # Support `python main.py` when launched from the app directory.
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    from app.real_ui import main


if __name__ == "__main__":
    main()