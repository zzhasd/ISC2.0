"""Run the incremental summary portrait experiment."""
if not __package__:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from identity_linkage.portrait_experiment import cli
    from identity_linkage.portrait_incremental_summary import run
else:
    from .portrait_experiment import cli
    from .portrait_incremental_summary import run

if __name__ == "__main__":
    cli("incremental_summary", run)
