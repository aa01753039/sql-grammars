import json
import os
from pathlib import Path
from tqdm import tqdm
from llama_cpp import Llama, LlamaGrammar

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