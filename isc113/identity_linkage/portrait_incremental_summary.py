"""B5. Rewrite the full current portrait at each source batch."""
from .core import save
from . import portrait_baseline_common
from .portrait_baseline_common import (
    INCREMENT, SUMMARY_BATCH, compact, entry_view, export_summary, leaf, reduce_entries,
)
from .portrait_experiment import chunks


def run(experiment, args):
    unique, attrs = experiment.attributes()
    config = dict(batch_size=SUMMARY_BATCH, state_target_characters=10000)
    if args.dry_run:
        experiment.log(f"[incremental_summary] {len(attrs)} validated attributes, {config}")
        return
    experiment.manifest("incremental_summary", config, "filtered ELARA v1 attributes", unique, [__file__, portrait_baseline_common.__file__])
    batches = iter(chunks(attrs, SUMMARY_BATCH))
    current = leaf(experiment, next(batches), "attributes", 1)
    for index, batch in enumerate(batches, 2):
        old = entry_view(current)
        refs = {key: row["refs"] for key, row in old.items()}
        refs.update({row["unique_id"]: [row["unique_id"]] for row in batch})
        current = reduce_entries(
            experiment, f"incremental/batch/{index:03d}", INCREMENT,
            dict(portrait=compact(old), attributes=batch, target_statement_characters=config["state_target_characters"]),
            refs,
        )
        save(experiment.output / "states" / f"{index:03d}.json", current)
        experiment.log(f"[incremental_summary] updated batch {index:03d}: {len(current)} entries")
    export_summary(experiment, current, unique)
