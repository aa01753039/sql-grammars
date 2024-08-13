import json
import os
import re
import sqlite3
import time
from pathlib import Path

import torch
from tqdm import tqdm
from transformers_cfg.generation.logits_process import GrammarConstrainedLogitsProcessor
from transformers_cfg.grammar_utils import IncrementalGrammarConstraint

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    pipeline,
    set_seed,
)

set_seed(12)


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


def keep_after_select(text):
    keyword = "SELECT"
    index = text.find(keyword)
    if index != -1:
        return text[index:]
    else:
        return text


def keep_after_last_occurrence(input_str: str) -> str:
    """
    Returns the substring after the last occurrence of the search_str in input_str.

    Parameters:
    input_str (str): The input string to search within.
    search_str (str): The string to find the last occurrence of.

    Returns:
    str: The substring after the last occurrence of search_str.
    """
    search_str = "Modified SQLite query:"
    last_index = input_str.rfind(search_str)
    if last_index == -1:
        return ""
    return input_str[last_index + len(search_str) :]


class Text2SQL:
    """
    Converts natural language questions into SQL queries using an LLM.

    This class handles:
        * Initialization of the LLM and tokenizer
        * Loading of questions and grammars
        * Generation of SQL answers
        * Output management (JSON, TXT)
    """

    def __init__(
        self,
        model_id,
        predicted_path,
        grammar_directory=None,
        db_directory=None,
        prompt_template=None,
    ):
        """
        Initializes the Text2SQL object.

        Args:
            model_id (str): Identifier for the pretrained language model.
            predicted_path (str): Directory to save prediction outputs.
            grammar_directory (str, optional): Path to grammar files (if used).
            db_directory (str, optional): Path to SQLite database files (if used).
            prompt_template (str, optional): Template for formatting question prompts.
        """
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        print("Loading Quantization model")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        print(torch.cuda.is_available())

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.tokenizer.pad_token = self.tokenizer.eos_token
        # some models that uses LlamaTokenizer needs this
        # self.tokenizer.padding_side = "right"

        self.llm = AutoModelForCausalLM.from_pretrained(
            model_id, quantization_config=bnb_config, device_map="auto"
        )
        # self.llm = AutoModelForCausalLM.from_pretrained(model_id).to(self.device)
        # some models needs this
        # # self.llm.generation_config.pad_token_id = self.llm.generation_config.eos_token_id
        # self.llm.resize_token_embeddings(len(self.tokenizer))

        # if model_id contains "instruct" set Instruction to True
        self.instruct = False
        if "instruct" in model_id.lower():
            self.instruct = True
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
        """
        Reads questions from a JSON file and stores them in the object.

        Args:
            questions_file (str): Path to the JSON file containing questions.
        """
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
        """
        Retrieves the embedded grammar for a specific database from the grammar directory.

        Args:
            db_id (str): Identifier for the database.

        Returns:
            str: The embedded grammar as a string, or None if not found.
        """
        if self.grammar_directory:
            grammar_path = os.path.join(self.grammar_directory, f"{db_id}.ebnf")

            if os.path.exists(grammar_path):
                # Load json grammar
                with open(grammar_path, "r", encoding="utf-8-sig") as file:
                    grammar = file.read()
        return grammar

    def get_base_grammar(self):
        """
        Retrieves the base grammar from the grammar directory.

        Returns:
            str: The base grammar as a string, or None if not found.
        """
        if self.grammar_directory:
            grammar_path = self.grammar_directory
            if os.path.exists(grammar_path):
                with open(grammar_path, "r", encoding="utf-8-sig") as file:
                    grammar = file.read()
        return grammar

    def get_ddl_statements_with_retries(
        self, database_path, max_retries=15, max_directories=15
    ):
        def get_ddl_statements(database_path):
            """
            Retrieves DDL statements for all tables in an SQLite database.

            Args:
                database_path (str): Path to the SQLite database file.

            Returns:
                str: Concatenated DDL statements for all tables.
            """
            # Connect to the SQLite database
            conn = sqlite3.connect(database_path)
            cursor = conn.cursor()

            # Query the sqlite_master table to get the names and DDL statements for all tables
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            # Close the connection
            conn.close()

            # Join all the DDL statements into a single string
            ddl_statements = ""
            for table in tables:
                ddl_statements += table[1] + "\n"

            return ddl_statements

        retries = 0
        base_path, db_name = os.path.split(database_path)

        while retries < max_retries:
            try:
                ddl_statements = get_ddl_statements(database_path)
                return ddl_statements
            except sqlite3.OperationalError as e:
                if "disk I/O error" in str(e):
                    retries += 1
                    time.sleep(1)
                    continue
                else:
                    return f"OperationalError: {e}"
            except sqlite3.DatabaseError as e:
                if "database disk image is malformed" in str(e):
                    retries += 1
                    time.sleep(1)
                    continue
                else:
                    return f"DatabaseError: {e}"

        for i in range(2, max_directories + 1):
            new_base_path = f"{base_path}{i}"
            new_db_path = os.path.join(new_base_path, db_name)
            retries = 0
            while retries < max_retries:
                try:
                    ddl_statements = get_ddl_statements(new_db_path)
                    return ddl_statements
                except sqlite3.OperationalError as e:
                    if "disk I/O error" in str(e):
                        retries += 1
                        print("Retrying", retries, "error:", str(e))
                        time.sleep(1)
                        continue
                    else:
                        return f"OperationalError: {e}"
                except sqlite3.DatabaseError as e:
                    if "database disk image is malformed" in str(e):
                        retries += 1
                        print("Retrying", retries, "error:", str(e))
                        time.sleep(1)
                        continue
                    else:
                        return f"DatabaseError: {e}"

        return f"Failed after trying {max_directories} directories"

    def execute_sql_query_with_retries(
        self, query: str, db_path: str, max_retries=15, max_directories=15
    ):
        def execute_sql_query(query: str, db_path: str):
            try:
                # Connect to the SQLite database
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Execute the SQL query
                cursor.execute(query)

                # Commit the changes
                conn.commit()

                # Close the connection
                conn.close()

                return None
            except sqlite3.Error as e:
                return str(e)

        retries = 0
        base_path, db_name = os.path.split(db_path)

        while retries < max_retries:
            error = execute_sql_query(query, db_path)
            if error is None:
                return None
            elif (
                "disk I/O error" in error
                or "database disk image is malformed" in error
                or "unable to open database file" in error
            ):
                retries += 1
                print("Retrying", retries, "error:", error)
                time.sleep(1)
                continue
            else:
                return error

        for i in range(2, max_directories + 1):
            new_base_path = f"{base_path}{i}"
            new_db_path = os.path.join(new_base_path, db_name)
            retries = 0
            while retries < max_retries:
                error = execute_sql_query(query, new_db_path)
                if error is None:
                    return None
                elif (
                    "disk I/O error" in error
                    or "database disk image is malformed" in error
                    or "unable to open database file" in error
                ):
                    retries += 1
                    time.sleep(1)
                    continue
                else:
                    return error

        # Return None if the last attempt still gives disk error or database malformed error
        return None

    def get_answers(self):
        """
        Generates SQL answers for each question and saves them in JSON format.
        """
        print("NL2SQL")
        if self.instruct:
            print("Instruction mode enabled")
        # Create a dictionary to store the answers
        answers_list = []

        # iterate over the questions dictionary
        for question in tqdm(
            self.questions, desc=f"Answering {len(self.questions)} questions"
        ):
            outputs_history = []
            # get the answer for each question
            question_id = question["id"]
            question_db = question["db_id"]
            user_question = question["question"]

            db_path = os.path.join(
                self.db_directory, question_db, f"{question_db}.sqlite"
            )
            schema = self.get_ddl_statements_with_retries(db_path)

            prompt = user_question
            if self.prompt_template:
                prompt = self.prompt_template.format(
                    question=user_question, schema=schema
                )

            attempts = 3
            last_prompt = prompt

            while attempts > 0:
                print(f"Question: {user_question}")
                print(f"Attempt: {4-attempts}")
                print(f"Prompt: {last_prompt}")
                print(f"length: {int(len(last_prompt)/2.8)}")

                pipe = pipeline(
                    "text-generation",
                    model=self.llm,
                    tokenizer=self.tokenizer,
                    device_map="auto",
                    max_length=int(len(last_prompt) / 2.8),
                    batch_size=2,
                )
                messages = [last_prompt]

                if self.instruct:
                    messages = [
                        {
                            "role": "system",
                            "content": "Your role is a natural language to SQL translator who is an expert in writing SQL queries in SQLite dialect. For the given schema, output the SQL query you need to answer the problem.",
                        },
                        {"role": "user", "content": last_prompt},
                    ]

                # if grammar_directory is a directory get_embedded_grammar if grammar_directory is a file get_base_grammar
                if self.grammar_directory:
                    grammar_path = Path(self.grammar_directory)
                    if grammar_path.is_dir():
                        grammar_str = self.get_embedded_grammar(question["db_id"])
                    elif grammar_path.is_file():
                        grammar_str = self.get_base_grammar()
                    grammar = IncrementalGrammarConstraint(
                        grammar_str, "root", self.tokenizer
                    )
                    grammar_processor = GrammarConstrainedLogitsProcessor(grammar)

                    generation = pipe(
                        messages,
                        do_sample=False,
                        logits_processor=[grammar_processor],
                        truncation=True,
                        temperature=None,
                        top_p=None,
                    )
                else:
                    generation = pipe(
                        messages,
                        do_sample=False,
                        truncation=True,
                        temperature=None,
                        top_p=None,
                    )

                # get output

                if self.instruct:
                    answer = generation[0]["generated_text"][-1]["content"]
                    full_answer = (
                        generation[0]["generated_text"][-2]["content"]
                        + " "
                        + generation[0]["generated_text"][-1]["content"]
                    )
                    outputs_history.append(full_answer)
                else:
                    answer = generation[0][0]["generated_text"]

                    outputs_history.append(answer)

                cleaned_answer = keep_after_select(answer)

                if attempts == 2:
                    if self.instruct:
                        cleaned_answer = keep_after_last_occurrence(full_answer)
                    else:
                        cleaned_answer = keep_after_last_occurrence(answer)

                cleaned_answer = (
                    re.sub(r"\n+", "\n", cleaned_answer)
                    .replace("\n", " ")
                    .replace("\r", " ")
                )

                print(f"Answer: {cleaned_answer}")

                error = self.execute_sql_query_with_retries(cleaned_answer, db_path)

                print(f"Error: {error}")
                if error is None:
                    # store the answer in the dictionary
                    answers_list.append(
                        {
                            "id": question_id,
                            "db_id": question_db,
                            "question": user_question,
                            "attempts": 4 - attempts,
                            "outputs_history": outputs_history,
                            "answer": cleaned_answer,
                        }
                    )
                    break
                if attempts == 3:
                    if self.instruct:
                        last_prompt = f"""{full_answer}
        Encountered an error: {error}. 
        To address this, please generate an alternative SQL query response that avoids this specific error. 
        Follow the instructions mentioned above to remediate the error. 

        Modify the below SQL query to resolve the issue:
        {cleaned_answer}

        Ensure the revised SQL query aligns precisely with the requirements outlined in the initial question.
        Modified SQLite query:"""
                    else:
                        # Prepare the new prompt for the next iteration
                        last_prompt = f"""{answer}
            Encountered an error: {error}. 
            To address this, please generate an alternative SQL query response that avoids this specific error. 
            Follow the instructions mentioned above to remediate the error. 

            Modify the below SQL query to resolve the issue:
            {cleaned_answer}

            Ensure the revised SQL query aligns precisely with the requirements outlined in the initial question.
            Modified SQLite query:"""
                    attempts -= 1
                else:
                    last_prompt = (
                        self.prompt_template.format(
                            question=user_question, schema=schema
                        )
                        + "\n\n"
                    )
                    attempts -= 1

            if attempts == 0:
                answers_list.append(
                    {
                        "id": question_id,
                        "db_id": question_db,
                        "question": user_question,
                        "attempts": 4 - attempts,
                        "outputs_history": outputs_history,
                        "answer": cleaned_answer,
                    }
                )

            # save the answers_dict to a json file after each answer
            with open(self.json_output, "w") as file:
                json.dump(answers_list, file, indent=2)
        print("Predictions saved to ", self.json_output)

    def convert_json_to_txt(self):
        """
        Converts the JSON output file to a TXT file with only SQL answers.
        """
        # read the answers from the json file
        with open(self.json_output, "r") as file:
            answers = json.load(file)

        # write the answers to the txt file
        with open(self.txt_output, "w") as file:
            for answer in answers:
                file.write(
                    answer["answer"].replace("\n", " ").replace("\r", " ") + "\n"
                )
        print(f"Answers written to {self.txt_output}")

    def predict(self, question_file):
        """
        Executes the prediction pipeline: reads questions, gets answers, saves output.

        Args:
            question_file (str): Path to the JSON file containing questions.
        """
        # read the questions from the json file
        self.read_questions(question_file)
        # get the answers for the questions
        self.get_answers()
