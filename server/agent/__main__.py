"""Operator commands.

python -m agent migrate                      apply the database migrations
python -m agent load vexcode-vr FILE...      keep the records in NDJSON log files
python -m agent sync vexcode-vr              read every new record from the source
"""

import json
import sys
from pathlib import Path

from agent import db, environments
from agent.events import parse_records


def load(environment_id: str, paths: list[str]) -> None:
    env = environments.all_environments()[environment_id]
    for path in paths:
        lines = [line for line in Path(path).read_text().splitlines() if line.strip()]
        records = [json.loads(line) for line in lines]
        rows, skipped = parse_records([(r, str(r["id"])) for r in records], env)
        print(f"{path}: {db.insert_events(rows)} new, {sum(skipped.values())} skipped")


def main(args: list[str]) -> None:
    match args:
        case ["migrate"]:
            print("\n".join(db.migrate()) or "nothing to apply")
        case ["load", environment_id, *paths] if paths:
            load(environment_id, paths)
        case ["sync", environment_id]:
            print(f"{environments.all_environments()[environment_id].sync()} new records")
        case _:
            sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
