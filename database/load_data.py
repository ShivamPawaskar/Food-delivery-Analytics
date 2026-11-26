"""Load latest Set 2 ETL CSV outputs into PostgreSQL."""
import json

from database.connection import get_engine
from database.loader import check_data_consistency, load_processed_outputs
from database.setup import initialize_schema


def main():
    engine = get_engine()
    try:
        initialize_schema(engine)
        loaded = load_processed_outputs(engine)
        consistency = check_data_consistency(engine)
        print(json.dumps({"load": loaded, "consistency": consistency}, indent=2, default=str))
        if not consistency["reconciled"] or not consistency["postgres_counts_match_current_csv"]:
            raise SystemExit("Database load finished, but record counts do not reconcile.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
