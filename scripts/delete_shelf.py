"""Delete shelves, with every image and scan saved under them.

Usage: LACUNA_DATABASE_URL=... uv run python scripts/delete_shelf.py live-check other-shelf

Asks before deleting unless --yes. Never prints the database URL.
"""

import argparse

from sqlalchemy.engine import make_url

from lacuna.config import Settings
from lacuna.db.session import make_engine, make_sessionmaker
from lacuna.services import NotFoundError, delete_shelf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("codes", nargs="+", help="shelf codes to delete")
    parser.add_argument("--yes", action="store_true", help="don't ask first")
    args = parser.parse_args()

    settings = Settings()
    url = make_url(settings.database_url)
    where = f"{url.get_backend_name()} database {url.database!r}"
    if not args.yes and input(f"Delete {', '.join(args.codes)} from the {where}? [y/N] ") != "y":
        raise SystemExit("nothing deleted")

    sessions = make_sessionmaker(make_engine(settings.database_url))
    with sessions() as session:
        for code in args.codes:
            try:
                print(f"{code}: deleted with {delete_shelf(session, code)} scans")
            except NotFoundError:
                print(f"{code}: no such shelf, skipped")


if __name__ == "__main__":
    main()
