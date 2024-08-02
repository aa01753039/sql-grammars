import os
import sqlite3


class SQLCFG:
    """
    Generates Context-Free Grammar (CFG) files for SQL parsing based on SQLite database schemas.

    This class handles:
        * Extraction of schema information (tables, columns) from databases.
        * Replacement of placeholders in a grammar template with extracted schema details.
        * Generation and saving of CFG files for each database.

    Args:
        grammar_template_path (str): Path to the grammar template file.
        db_base_path (str): Base directory containing database folders.
        grammar_directory (str): Directory to store generated grammar files.
    """
    def __init__(self, grammar_template_path, db_base_path, grammar_directory):
        """
        Initializes the SQLCFG object.

        Loads the grammar template and sets paths for the database and grammar directories.
        """
        with open(grammar_template_path, "r") as file:
            self.grammar_template = file.read()

        self.db_base_path = db_base_path
        self.grammar_directory = grammar_directory

        # Ensure the grammar directory exists
        os.makedirs(grammar_directory, exist_ok=True)

    def extract_schema(self, db_path):
        """
        Extracts table and column information from an SQLite database.

        Args:
            db_path (str): Path to the SQLite database file.

        Returns:
            dict: A dictionary where keys are table names and values are lists of column names.
        """
        """Extracts tables and columns from the SQLite database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Extract table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        # Extract columns for each table
        schema = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            schema[table_name] = [
                col[1] for col in columns
            ]  # Assuming col[1] is the column name

        conn.close()
        return schema

    def get_table_names(self, schema):
        """
        Extracts table names from the schema dictionary.

        Args:
            schema (dict): The schema dictionary containing table and column information.

        Returns:
            list: A list of table names.
        """
        # Extract table names
        return list(schema.keys())

    def get_column_names(self, schema, table_names):
        """
        Extracts column names from the schema for specified tables.

        Args:
            schema (dict): The schema dictionary.
            table_names (list): A list of table names for which to extract columns.

        Returns:
            list: A list of all column names from the specified tables.
        """
        # Extract column names for each table
        column_names = []
        for table in table_names:
            column_names.extend(schema[table])
        return column_names

    def get_placeholders(self, table_names, schema):
        """
        Prepares placeholders for table names and column names to be used in the grammar template.
        
        Args:
            table_names (list): List of table names.
            schema (dict): Dictionary containing table and column information.

        Returns:
            tuple: A tuple containing two strings:
                - tables_placeholder: A string containing pipe-separated table names.
                - columns_placeholder: A string containing pipe-separated column names.
        """
        # Prepare placeholders content
       
        tables_placeholder = " | ".join(f'"{tbl}"' for tbl in table_names)
        for table in table_names:
            columns_placeholder = ' | '.join(f'"{col}"' for col in schema[table])
        

        return  tables_placeholder, columns_placeholder

    def replace_placeholders(self, schema):
        """
        Replaces placeholders in the grammar template with the actual table and column names from the schema.

        Args:
            schema (dict): The schema dictionary.

        Returns:
            str: The grammar template with placeholders replaced.
        """
        # Replace placeholders with actual content
        table_names = self.get_table_names(schema)
        tables_placeholder,columns_placeholder = (
            self.get_placeholders( table_names, schema)
        )
        
        grammar = self.grammar_template.replace("TABLE_NAMES_PLACEHOLDER", tables_placeholder)
        grammar = grammar.replace("COLUMNS_PLACEHOLDER", columns_placeholder)
        return grammar

    def process_databases(self):
        """
        Processes all SQLite databases in the specified base path.

        For each database:
            - Extracts the schema (tables and columns).
            - Replaces placeholders in the grammar template with the extracted schema information.
            - Writes the generated grammar to a file in the specified grammar directory.
        """
        # Iterate over all directories in the base path
        for db_name in os.listdir(self.db_base_path):
            db_dir = os.path.join(self.db_base_path, db_name)
            db_file = os.path.join(db_dir, f"{db_name}.sqlite")
            if os.path.isfile(db_file):
                schema = self.extract_schema(db_file)
                grammar = self.replace_placeholders(schema)
                grammar_path = os.path.join(self.grammar_directory, f"{db_name}.ebnf")
                self.write_grammar(grammar, grammar_path)

    def write_grammar(self, grammar, grammar_path):
        """
        Writes the generated grammar to a file.

        Args:
            grammar (str): The generated grammar content.
            grammar_path (str): The path to the file where the grammar will be saved.
        """
        # Ensure the directory exists before writing the grammar file
        os.makedirs(os.path.dirname(grammar_path), exist_ok=True)
        # Write the grammar to the specified grammar file
        with open(grammar_path, "w") as file:
            file.write(grammar)
        print(f"Grammar saved to {grammar_path}")