import os
import sqlite3


class SQLCFG:
    def __init__(self, grammar_template_path, db_base_path, grammar_directory):
        with open(grammar_template_path, "r") as file:
            self.grammar_template = file.read()

        self.db_base_path = db_base_path
        self.grammar_directory = grammar_directory

        # Ensure the grammar directory exists
        os.makedirs(grammar_directory, exist_ok=True)

    def extract_schema(self, db_path):
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
        # Extract table names
        return list(schema.keys())

    def get_column_names(self, schema, table_names):
        # Extract column names for each table
        column_names = []
        for table in table_names:
            column_names.extend(schema[table])
        return column_names

    def get_placeholders(self, table_names, schema):
        # Prepare placeholders content
       
        tables_placeholder = " | ".join(f'"{tbl}"' for tbl in table_names)
        for table in table_names:
            columns_placeholder = ' | '.join(f'"{col}"' for col in schema[table])
        

        return  tables_placeholder, columns_placeholder

    def replace_placeholders(self, schema):
        # Replace placeholders with actual content
        table_names = self.get_table_names(schema)
        tables_placeholder,columns_placeholder = (
            self.get_placeholders( table_names, schema)
        )
        
        grammar = self.grammar_template.replace("TABLE_NAMES_PLACEHOLDER", tables_placeholder)
        grammar = grammar.replace("COLUMNS_PLACEHOLDER", columns_placeholder)
        return grammar

    def process_databases(self):
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
        # Ensure the directory exists before writing the grammar file
        os.makedirs(os.path.dirname(grammar_path), exist_ok=True)
        # Write the grammar to the specified grammar file
        with open(grammar_path, "w") as file:
            file.write(grammar)
        print(f"Grammar saved to {grammar_path}")