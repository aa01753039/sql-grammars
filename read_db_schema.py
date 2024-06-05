"""
This python script will reaad a .gbnf file and a sqlite db file.
It will read db schema from the sqlite file and embed it on the .gbnf file.

Author: Lesly Guerrero
"""

import sqlite3
import sys
import os
import re
from pathlib import Path

class SQLGrammar:
    def __init__(self,grammar_path: Path) -> None:
        self.grammar_path = grammar_path
        self.grammar_str = open(grammar_path, 'r').read()
        self.schema = {}
    
    def get_db_schema(self, db_path: Path) -> None:
        """Extracts tables and columns from the SQLite database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Extract table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        # Extract columns for each table
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            self.schema[table_name] = [col[1] for col in columns]  # Assuming col[1] is the column name
        
        conn.close()

        def generate_grammar(self) -> None:
            """Generates the grammar string with the extracted schema."""
            # In the format: table-name ::= "table1" | "table2" | "table3"
            # column-name ::= "column1" | "column2" | "column3"
            # column-alias ::= "alias1" | "alias2" | "alias3"
            # table-alias ::= "alias1" | "alias2" | "alias3"

            for table, columns in self.schema.items():
                table_str = f"{table} ::= "
                table_str += " | ".join([f'"{col}"' for col in columns])
                self.grammar_str = re.sub(f"{table} ::= .*", table_str, self.grammar_str)
    


