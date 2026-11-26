"""Run the direct portrait experiment."""
if not __package__:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from identity_linkage.portrait_experiment import cli
    from identity_linkage.portrait_direct import configure, run
else:
    from .portrait_experiment import cli
    from .portrait_direct import configure, run

if __name__ == "__main__":
    cli("direct", run, configure)
