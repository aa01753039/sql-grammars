# import necessary libraries
import argparse
import json
import os

from llama_cpp import Llama, LlamaGrammar
from tqdm import tqdm
import sqlite3


class SQLGrammar:
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
            schema[table_name] = [col[1] for col in columns]  # Assuming col[1] is the column name
        
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

    def get_placeholders(self, column_names, table_names):
        # Prepare placeholders content
        columns_placeholder = " | ".join(f'"{col}"' for col in column_names)
        tables_placeholder = " | ".join(f'"{tbl}"' for tbl in table_names)
        aliases_placeholder = columns_placeholder

        return columns_placeholder, tables_placeholder, aliases_placeholder

    def replace_placeholders(self, schema):
        # Replace placeholders with actual content
        table_names = self.get_table_names(schema)
        column_names = self.get_column_names(schema, table_names)
        columns_placeholder, tables_placeholder, aliases_placeholder = self.get_placeholders(column_names, table_names)
        
        grammar = self.grammar_template.replace("COLUMN_NAMES_PLACEHOLDER", columns_placeholder)
        grammar = grammar.replace("TABLE_NAMES_PLACEHOLDER", tables_placeholder)
        grammar = grammar.replace("ALIAS_NAMES_PLACEHOLDER", aliases_placeholder)
        
        return grammar

    def process_databases(self):
        # Iterate over all directories in the base path
        for db_name in os.listdir(self.db_base_path):
            db_dir = os.path.join(self.db_base_path, db_name)
            db_file = os.path.join(db_dir, f"{db_name}.sqlite")
            if os.path.isfile(db_file):
                schema = self.extract_schema(db_file)
                grammar = self.replace_placeholders(schema)
                grammar_path = os.path.join(self.grammar_directory, f"{db_name}.gbnf")
                self.write_grammar(grammar, grammar_path)

    def write_grammar(self, grammar, grammar_path):
        # Ensure the directory exists before writing the grammar file
        os.makedirs(os.path.dirname(grammar_path), exist_ok=True)
        # Write the grammar to the specified grammar file
        with open(grammar_path, "w") as file:
            file.write(grammar)
        print(f"Grammar saved to {grammar_path}")


class LLMResponse:
    def __init__(self, llm_repo, llm_file, predicted_path, grammar_directory=None):
        self.llm = Llama.from_pretrained(
            repo_id=llm_repo, filename=llm_file, verbose=False
        )
        self.questions = {}
        self.grammar_directory = grammar_directory
        self.predicted_path = predicted_path

        # Ensure the predicted_path exists
        os.makedirs(os.path.dirname(predicted_path), exist_ok=True)

    def read_questions(self, questions_file):
        print("Reading questions from ", questions_file)
        # read the questions from the json file
        with open(questions_file, "r") as file:
            json_questions = json.load(file)

        # extract db_id and question from the json file
        for question in json_questions:
            # add each db_id with all its questions to the questions dictionary
            if question["db_id"] not in self.questions:
                self.questions[question["db_id"]] = []
            self.questions[question["db_id"]].append(question["question"])

    def get_answers(self):
        print("NL2SQL")
        # iterate over the questions dictionary
        with open(self.predicted_path, "w") as file:
            i = 1
            for db_id, questions in tqdm(
                self.questions.items(), desc="Answering questions"
            ):
                # load the specific grammar for the db_id if available
                grammar = None
                if self.grammar_directory:
                    grammar_path = os.path.join(self.grammar_directory, f"{db_id}.gbnf")
                    if os.path.exists(grammar_path):
                        print("DB ID: ", db_id, "Grammar Path: ", grammar_path)
                        grammar = LlamaGrammar.from_file(grammar_path)

                # iterate over the questions
                for question in tqdm(questions,desc=f"Answering question {i}/{len(questions)}"):
                    # get the answer for each question
                    # prompt the model
                    answer = self.llm(
                        question,  # prompt
                        grammar=grammar,
                        max_tokens=-1,  # as necessary tokens
                    )
                    # write the answer directly to the file
                    file.write(f"{answer['choices'][0]['text']}\n")
                file.write("\n")
                i += 1
        print("Predictions saved to ", self.predicted_path)

    def predict(self, question_file):
        # read the questions from the json file
        self.read_questions(question_file)
        # get the answers for the questions
        self.get_answers()



if __name__ == "__main__":
    # parse the arguments: databases folder path, questions json file path, and the output file path, and if use_embedded_grammar is set
    parser = argparse.ArgumentParser(description="Evaluate grammar")
    parser.add_argument(
        "--llm_repo",
        type=str,
        help="The repository id of the LLM model",
    )
    parser.add_argument(
        "--llm_file",
        type=str,
        help="The file name of the LLM model",
    )
    parser.add_argument(
        "--grammar_template_path",
        type=str,
        help="The path to the grammar file",
        default=None,
        required=False,
    )
    parser.add_argument(
        "--db_base_path",
        type=str,
        help="The path to the database folder",
        default=None,
        required=False,
    )
    parser.add_argument(
        "--grammar_directory",
        type=str,
        help="The path to the embedded grammar directory",
        default=None,
        required=False,
    )
    parser.add_argument(
        "--questions_file",
        type=str,
        help="JSON file containing the questions",
    )
    parser.add_argument(
        "--predicted_path",
        type=str,
        help="Output  SQL .txt file path",
    )
    args = parser.parse_args()

    # create a SQLGrammar object if grammar_directory is provided
    if args.grammar_directory:
        sql_grammar = SQLGrammar(
            args.grammar_template_path, args.db_base_path, args.grammar_directory
        )
        # write the grammar to the embedded grammar file
        sql_grammar.process_databases()

    # create a LLMResponse object
    llm_response = LLMResponse(
        args.llm_repo, args.llm_file, args.predicted_path, args.grammar_directory
    )
    # read the questions from the json file
    llm_response.predict(args.questions_file)
