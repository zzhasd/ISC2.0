"""B1. Full-context Direct with historical replay and an optional live run."""
from .core import load
from .portrait_historical import historical
from .portrait_summary import validate_portraits


def configure(parser):
    parser.add_argument("--live", action="store_true", help="Retry the exact frozen request in a separate --output")


def run(experiment, args):
    if not args.live or args.dry_run:
        historical(experiment, args, "direct", "direct")
        return
    if args.output is None or experiment.client is None:
        raise ValueError("--live needs TOKEN_PLAN_API_KEY and a separate --output directory")

    dialogues = experiment.dialogues()
    inputs = {"dialogues": dialogues}
    payload = load(experiment.source / "direct_request.json")
    experiment.manifest("direct", {"frozen_single_call": True}, "frozen A-only dialogues", dialogues, [__file__])
    result, _ = experiment.client.call(
        "direct/live", payload, lambda obj: validate_portraits(obj, "direct", inputs, []),
    )
    experiment.export(result["portraits"], audit={"input_dialogues": len(dialogues)})
