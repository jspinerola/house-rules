"""python -m app.seed: (re)seed the SQLite store from fixtures/scenario.json. Repeatable."""
from __future__ import annotations

from .db import SqliteStore


def main() -> None:
    store = SqliteStore()
    store.reset()
    for r in store.roommates():
        print(f"{r.id:7} checking ${r.checking:,.2f}  next payday {r.next_payday}  handle {r.handle}")
    print(f"clock {store.today()}  db {store.path}")


if __name__ == "__main__":
    main()
