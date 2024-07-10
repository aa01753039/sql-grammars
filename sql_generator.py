import argparse
import json
import os
import sqlite3
from pathlib import Path

from llama_cpp import Llama, LlamaGrammar
from tqdm import tqdm


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

    def get_placeholders(self, column_names, table_names, schema):
        # Prepare placeholders content
       
        tables_placeholder = " | ".join(f'"{tbl}"' for tbl in table_names)
        
        table_columns_placeholder = " | ".join(f'{tbl.replace("_","-")}-columns' for tbl in table_names)
        
        #create a placeholder for each table and its columns like: club-column ::= "Club_ID" | "Name" | "Manager" | "Captain" | "Manufacturer" | "Sponsor"/n
        column_names_placeholder = ""
        for table in table_names:
            column_names_placeholder += f'{table.replace("_","-")}-columns ::= ' + ' | '.join(f'"{col} "' for col in schema[table])
            column_names_placeholder += '\n'

        return  tables_placeholder, table_columns_placeholder, column_names_placeholder

    def replace_placeholders(self, schema, db_name):
        # Replace placeholders with actual content
        table_names = self.get_table_names(schema)
        column_names = self.get_column_names(schema, table_names)
        schema_placeholder = '"'+db_name+'"'
        tables_placeholder,tables_columns_placeholder,column_names_placeholder = (
            self.get_placeholders(column_names, table_names, schema)
        )

        
        
        
        grammar = self.grammar_template.replace("SCHEMA_NAMES_PLACEHOLDER", schema_placeholder)
        grammar = grammar.replace("TABLE_NAMES_PLACEHOLDER", tables_placeholder)
        grammar = grammar.replace("TABLE_COLUMNS_PLACEHOLDER", tables_columns_placeholder)
        grammar = grammar.replace(
            "COLUMN_NAMES_PLACEHOLDER", column_names_placeholder
        )
        return grammar

    def process_databases(self):
        # Iterate over all directories in the base path
        for db_name in os.listdir(self.db_base_path):
            db_dir = os.path.join(self.db_base_path, db_name)
            db_file = os.path.join(db_dir, f"{db_name}.sqlite")
            if os.path.isfile(db_file):
                schema = self.extract_schema(db_file)
                grammar = self.replace_placeholders(schema,db_name)
                grammar_path = os.path.join(self.grammar_directory, f"{db_name}.gbnf")
                self.write_grammar(grammar, grammar_path)

    def write_grammar(self, grammar, grammar_path):
        # Ensure the directory exists before writing the grammar file
        os.makedirs(os.path.dirname(grammar_path), exist_ok=True)
        # Write the grammar to the specified grammar file
        with open(grammar_path, "w") as file:
            file.write(grammar)
        print(f"Grammar saved to {grammar_path}")


class LLMResponser:
    def __init__(self, llm_repo, llm_file, predicted_path, grammar_directory=None):
        self.llm = Llama.from_pretrained(
            repo_id=llm_repo, filename=llm_file, verbose=False
        )
        self.questions = []
        self.grammar_directory = grammar_directory
        self.json_output = predicted_path + "/output.json"
        self.txt_output = predicted_path + "/output.txt"

        # Ensure the predicted_path exists
        os.makedirs(os.path.dirname(self.json_output), exist_ok=True)
        os.makedirs(os.path.dirname(self.txt_output), exist_ok=True)

    def read_questions(self, questions_file):
        print("Reading questions from ", questions_file)
        # read the questions from the json file
        with open(questions_file, "r") as file:
            json_questions = json.load(file)

        # add an id to each question in jsson_questions
        for i, question in enumerate(json_questions):
            question["id"] = i

        # extract id, db_id, and question from the json file
        for question in json_questions:
            self.questions.append(
                {
                    "id": question["id"],
                    "db_id": question[
                        "db_id"
                    ],  # "db_id" is the key for the database id in the json file
                    "question": question["question"],
                }
            )

    def get_embedded_grammar(self, db_id):
        if self.grammar_directory:
            grammar_path = os.path.join(self.grammar_directory, f"{db_id}.gbnf")
            if os.path.exists(grammar_path):
                grammar = LlamaGrammar.from_file(grammar_path, verbose=False)
        return grammar

    def get_base_grammar(self):
        if self.grammar_directory:
            grammar_path = (self.grammar_directory)
            if os.path.exists(grammar_path):
                grammar = LlamaGrammar.from_file(grammar_path, verbose=False)
        return grammar

    def get_answers(self):
        print("NL2SQL")
        # Create a dictionary to store the answers
        answers_list = []

        # iterate over the questions dictionary
        for question in tqdm(
            self.questions, desc=f"Answering {len(self.questions)} questions"
        ):
            
            # if grammar_directory is a directory get_embedded_grammar if grammar_directory is a file get_base_grammar
            if self.grammar_directory:
                grammar_path = Path(self.grammar_directory)
                if grammar_path.is_dir():
                    grammar = self.get_embedded_grammar(question["db_id"])
                elif grammar_path.is_file():
                    grammar = self.get_base_grammar()
            else:
                grammar = None

            # get the answer for each question
            question_id = question["id"]
            question_db = question["db_id"]
            question = question["question"]
            # get the answer for each question
            answer = self.llm(
                question,  # prompt
                grammar=grammar,
                max_tokens=-1,  # as necessary tokens
                seed=0,  # seed for reproducibility
            )
            # store the answer in the dictionary
            answers_list.append(
                {
                    "id": question_id,
                    "db_id": question_db,
                    "question": question,
                    "answer": answer["choices"][0]["text"],
                }
            )

            # save the answers_dict to a json file after each answer
            with open(self.json_output, "w") as file:
                json.dump(answers_list, file, indent=2)
        print("Predictions saved to ", self.json_output)

    def convert_json_to_txt(self):
        # read the answers from the json file
        with open(self.json_output, "r") as file:
            answers = json.load(file)

        # write the answers to the txt file
        with open(self.txt_output, "w") as file:
            for answer in answers:
                file.write(answer["answer"].replace("\n", "") + "\n")
        print(f"Answers written to {self.txt_output}")

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
        help="Output directory for the predictions ",
    )

    args = parser.parse_args()

    # create a SQLGrammar object if grammar_directory is provided
    if args.grammar_directory:
        if Path(args.grammar_directory).is_dir():
            sql_grammar = SQLGrammar(
            args.grammar_template_path, args.db_base_path, args.grammar_directory
        )
            # write the grammar to the embedded grammar file
            sql_grammar.process_databases()
            grammar_path = args.grammar_directory
    else:
        if args.grammar_template_path:
            grammar_path = args.grammar_template_path
        else:
            grammar_path = None

    # create a LLMResponse object
    llm_response = LLMResponser(
        args.llm_repo, args.llm_file, args.predicted_path, grammar_path
    )
    # read the questions from the json file
    llm_response.predict(args.questions_file)
    # convert the JSON file to a TXT file
    llm_response.convert_json_to_txt()
