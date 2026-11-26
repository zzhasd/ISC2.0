"""Run the agentic direct portrait experiment."""
if not __package__:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from identity_linkage.portrait_experiment import cli
    from identity_linkage.portrait_agentic_direct import run
else:
    from .portrait_experiment import cli
    from .portrait_agentic_direct import run

if __name__ == "__main__":
    cli("agentic_direct", run)
