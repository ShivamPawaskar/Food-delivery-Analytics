"""Compare current Set 2 CSV counts with PostgreSQL table counts."""
import json

from database.connection import get_engine
from database.loader import check_data_consistency


def main():
    engine = get_engine()
    try:
        result = check_data_consistency(engine)
        print(json.dumps(result, indent=2, default=str))
        if not result["reconciled"] or not result["postgres_counts_match_current_csv"]:
            raise SystemExit("Data consistency verification failed.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
