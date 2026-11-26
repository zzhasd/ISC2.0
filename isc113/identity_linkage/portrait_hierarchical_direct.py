"""B2. Map raw dialogue batches, then reduce their portraits in a fixed tree."""
from . import portrait_baseline_common
from .portrait_baseline_common import DIRECT_BATCH, export_direct, hierarchy, leaves


def run(experiment, args):
    dialogues = experiment.dialogues()
    config = dict(batch_size=DIRECT_BATCH, fan_in=3)
    if args.dry_run:
        experiment.log(f"[hierarchical_direct] {len(dialogues)} validated dialogues, {config}")
        return
    experiment.manifest("hierarchical_direct", config, "frozen A-only dialogues", dialogues, [__file__, portrait_baseline_common.__file__])
    partials = leaves(experiment, dialogues, "dialogues")
    export_direct(experiment, hierarchy(experiment, partials, config["fan_in"], "dialogues"), dialogues)
