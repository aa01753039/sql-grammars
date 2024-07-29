from core.SQLiteExec import SQLiteExec
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execution SQLite dialect accuracy")

    parser.add_argument(
        "--db", type=str, help="The path to the database file", required=True
    )
    parser.add_argument(
        "--sql", type=str, help="The path to the queries file", required=True
    )
    parser.add_argument(
        "--ids", type=str, help="The path to the database IDs file", required=True
    )

    args = parser.parse_args()

    executor = SQLiteExec(args.db)
    queries, db_ids = executor.read_queries_and_ids(args.sql, args.ids)
    results = executor.execute_queries(queries, db_ids)

    accuracy, successful_queries = executor.calculate_accuracy(results)

    print("\n\n\n****************** RESULTS ******************\n")
    print(f"Total queries: {len(results)}")
    print(f"% of executable queries: {accuracy * 100:.2f}%")
    print(f"Proportion of executable queries: {successful_queries}/{len(results)}")
