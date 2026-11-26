"""B4. Map batches of ELARA attributes, then reduce their portraits in a fixed tree."""
from . import portrait_baseline_common
from .portrait_baseline_common import SUMMARY_BATCH, export_summary, hierarchy, leaves


def run(experiment, args):
    unique, attrs = experiment.attributes()
    config = dict(batch_size=SUMMARY_BATCH, fan_in=3)
    if args.dry_run:
        experiment.log(f"[hierarchical_summary] {len(attrs)} validated attributes, {config}")
        return
    experiment.manifest("hierarchical_summary", config, "filtered ELARA v1 attributes", unique, [__file__, portrait_baseline_common.__file__])
    partials = leaves(experiment, attrs, "attributes")
    export_summary(experiment, hierarchy(experiment, partials, config["fan_in"], "attributes"), unique)
