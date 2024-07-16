import json
import os
import re
import sqlite3
from pathlib import Path

from llama_cpp import Llama, LlamaGrammar
from tqdm import tqdm


def remove_data_types(sql_definition):
    # Regex to find the column definitions and retain only the column names
    pattern = re.compile(
        r"`(\w+)`\s*(?:[A-Z]+\(.+?\)|[A-Z]+(?:\s+NOT\s+NULL)?(?:\s+DEFAULT\s+\S+)?)?\s*,?"
    )

    # Function to replace the column definitions with just column names
    def replacer(match):
        return f"`{match.group(1)}`,"

    # Process each table definition
    processed_definition = re.sub(pattern, replacer, sql_definition)

    # Clean up any trailing commas before closing parentheses
    processed_definition = re.sub(r",\s*\)", ")", processed_definition)
    # remove commas next to a (
    processed_definition = re.sub(r",\s*\(", "(", processed_definition)
    # from this pattern `product_id`,PRIMARY KEY , remove the  PRIMARY KEY , (it can be any other word)
    processed_definition = re.sub(r",(\w+) (\w+)", "", processed_definition)

    return processed_definition


class LLMResponser:
    def __init__(
        self,
        llm_repo,
        llm_file,
        predicted_path,
        grammar_directory=None,
        db_directory=None,
        prompt_template=None,
    ):
        self.llm = Llama.from_pretrained(
            repo_id=llm_repo, filename=llm_file, verbose=False
        )
        self.questions = []
        self.grammar_directory = grammar_directory
        self.json_output = predicted_path + "/output.json"
        self.txt_output = predicted_path + "/output.txt"
        self.prompt_template = prompt_template
        self.db_directory = db_directory

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
            grammar_path = self.grammar_directory
            if os.path.exists(grammar_path):
                grammar = LlamaGrammar.from_file(grammar_path, verbose=False)
        return grammar

    def get_ddl_statements(self, database_path):
        """
        Retrieve the DDL statements for all tables in the specified SQLite database.

        :param database_path: Path to the SQLite database file.
        :return: A dictionary with table names as keys and DDL statements as values.
        """
        # Connect to the SQLite database
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()

        # Query the sqlite_master table to get the names and DDL statements for all tables
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        # Close the connection
        conn.close()

        # join all the DDL statements into a single string
        ddl_statements = ""
        for table in tables:
            ddl_statements += table[1] + "\n"

        if len(ddl_statements) > 950:
            # Remove the data types from the DDL statements
            ddl_statements = remove_data_types(ddl_statements)
            # just keep the first 1000 characters
            ddl_statements = ddl_statements[:950]

        return ddl_statements

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

            prompt = question
            if self.prompt_template:
                db_path = os.path.join(
                    self.db_directory, question_db, f"{question_db}.sqlite"
                )
                schema = self.get_ddl_statements(db_path)
                prompt = self.prompt_template.format(question=question, schema=schema)

            # get the answer for each question
            answer = self.llm(
                prompt,  # prompt
                grammar=grammar,
                max_tokens=100,  # as necessary tokens
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
                file.write(answer["answer"].replace("\n", "").replace("\r", "") + "\n")
        print(f"Answers written to {self.txt_output}")

    def predict(self, question_file):
        # read the questions from the json file
        self.read_questions(question_file)
        # get the answers for the questions
        self.get_answers()
