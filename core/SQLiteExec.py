import sqlite3
import os


class SQLiteExec:
    def __init__(self, db_base_path):
        self.db_base_path = db_base_path

    def _connect_to_database(self, db_id):
        db_path = os.path.join(self.db_base_path, db_id, f"{db_id}.sqlite")
        try:
            connection = sqlite3.connect(db_path)
            print(f"Connected to database: {db_path}")
            return connection
        except sqlite3.Error as e:
            print(f"Error connecting to database {db_path}: {e}")
            return None

    def read_queries_and_ids(self, query_file_path, id_file_path):
        try:
            with open(query_file_path, "r") as query_file:
                queries = query_file.readlines()
            with open(id_file_path, "r") as id_file:
                db_ids = id_file.readlines()
            if len(queries) != len(db_ids):
                print(
                    "Error: The number of queries does not match the number of database IDs."
                )
                return [], []
            print(
                f"Read {len(queries)} queries and {len(db_ids)} database IDs from files."
            )
            return queries, db_ids
        except Exception as e:
            print(f"Error reading files: {e}")
            return [], []

    def execute_queries(self, queries, db_ids):
        results = []
        for query, db_id in zip(queries, db_ids):
            db_id = db_id.strip()
            connection = self._connect_to_database(db_id)
            if connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(query)
                    connection.commit()
                    results.append(1)
                except sqlite3.Error as e:
                    print(f"Error executing query: {query.strip()}\nError: {e}")
                    results.append(0)
                finally:
                    cursor.close()
                    connection.close()
            else:
                results.append(0)
        return results

    def calculate_accuracy(self, results):
        total_queries = len(results)
        if total_queries == 0:
            return 0, 0

        successful_queries = sum(results)
        accuracy = successful_queries / total_queries
        return accuracy, successful_queries
