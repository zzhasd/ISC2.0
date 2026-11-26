"""B3. Full-context two-stage Summary v2 with historical replay."""
from .portrait_historical import historical


def configure(parser):
    parser.add_argument("--live", action="store_true", help="Retry the original stages in a separate --output")


def run(experiment, args):
    if not args.live or args.dry_run:
        historical(experiment, args, "summary_v2", "summary")
        return
    if args.output is None or experiment.client is None:
        raise ValueError("--live needs TOKEN_PLAN_API_KEY and a separate --output directory")

    from . import subject_one_portrait_tokenplan_v1 as original
    from .core import load
    from .portrait_summary import compact_summary_request

    unique, _ = experiment.attributes()
    inputs = {"dialogues": experiment.dialogues()}
    if compact_summary_request(unique) != load(experiment.source / "summary_request.json"):
        raise ValueError("The existing Summary v2 code produces a different frozen request")
    experiment.manifest("summary_v2", {"frozen_two_stage": True}, "filtered ELARA v1 attributes", unique,
                        [__file__, original.__file__])
    original.generate_summary(experiment.output, inputs, experiment.client, unique)
    result = load(experiment.output / "summary_raw.json")["prediction"]
    experiment.export(result["portraits"], unique=unique, audit=load(experiment.output / "summary_report.json"))
