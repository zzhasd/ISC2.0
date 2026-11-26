"""Run the amem adapted portrait experiment."""
if not __package__:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from identity_linkage.portrait_experiment import cli
    from identity_linkage.portrait_amem_adapted import configure, run
else:
    from .portrait_experiment import cli
    from .portrait_amem_adapted import configure, run

if __name__ == "__main__":
    cli("amem_adapted", run, configure)
