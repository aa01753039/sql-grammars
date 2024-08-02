import sqlite3
import os


class SQLiteExec:
    """
    Executes SQL queries against multiple SQLite databases and tracks execution success.

    This class provides functionality for:
        * Connecting to SQLite databases based on IDs.
        * Reading queries and corresponding database IDs from files.
        * Executing queries against the appropriate databases.
        * Calculating the overall accuracy of query execution.
    """
    def __init__(self, db_base_path):
        """
        Initializes the SQLiteExec object.

        Args:
            db_base_path (str): The base directory where database folders are located.
        """
        self.db_base_path = db_base_path

    def _connect_to_database(self, db_id):
        """
        Connects to an SQLite database based on its ID.

        This is a private helper method.

        Args:
            db_id (str): The ID of the database to connect to.

        Returns:
            sqlite3.Connection: A connection object to the database, or None if connection fails.
        """
        db_path = os.path.join(self.db_base_path, db_id, f"{db_id}.sqlite")
        try:
            connection = sqlite3.connect(db_path)
            print(f"Connected to database: {db_path}")
            return connection
        except sqlite3.Error as e:
            print(f"Error connecting to database {db_path}: {e}")
            return None

    def read_queries_and_ids(self, query_file_path, id_file_path):
        """
        Reads SQL queries and corresponding database IDs from files.

        Args:
            query_file_path (str): Path to the file containing SQL queries, one per line.
            id_file_path (str): Path to the file containing database IDs, one per line.

        Returns:
            tuple: A tuple containing two lists:
                - queries (list): A list of SQL queries as strings.
                - db_ids (list): A list of database IDs as strings.

            If an error occurs during file reading or if the number of queries and IDs don't match,
            both lists will be empty.
        """
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
        """
        Executes a list of SQL queries against their respective SQLite databases.

        Args:
            queries (list): A list of SQL queries as strings.
            db_ids (list): A list of database IDs corresponding to the queries.

        Returns:
            list: A list of integers indicating the success of each query execution:
                - 1: Query executed successfully
                - 0: Query execution failed
        """
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
        """
        Calculates the accuracy of SQL query executions.

        Args:
            results (list): A list of integers (1 for success, 0 for failure) representing query execution outcomes.

        Returns:
            tuple: A tuple containing:
                - accuracy (float): The overall accuracy as a proportion of successful queries.
                - successful_queries (int): The number of successfully executed queries.
        """
        total_queries = len(results)
        if total_queries == 0:
            return 0, 0

        successful_queries = sum(results)
        accuracy = successful_queries / total_queries
        return accuracy, successful_queries
