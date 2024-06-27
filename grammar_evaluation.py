#import necessary libraries
from llama_cpp import Llama, LlamaGrammar
import json
import argparse
import re

class SQLGrammar:
    def __init__(self, grammar_path,db_path, grammar_embedded_path=None):
        
        with open(grammar_path, 'r') as file:
            self.grammar = file.read()

        self.grammar_embedded = grammar_embedded_path
        self.db_path = db_path
    
    def get_schema(self):
        # read the database schema in the database path inside the schema.sql file and extract the content as string
        with open(self.db_path+"schema.sql", 'r') as file:
            self.schema = file.read()
    
    def get_table_names(self):
        # Extract table names
        table_names = re.findall(r'CREATE TABLE "([^"]+)"', self.schema)
        return table_names

    def get_column_names(self, table_names):
        # Extract column names for each table
        column_names = []
        for table in table_names:
            table_schema = re.search(r'CREATE TABLE "{}" \((.*?)\);'.format(table), self.schema, re.DOTALL).group(1)
            columns = re.findall(r'"([^"]+)"', table_schema)
            column_names.extend(columns)
        return column_names
    
    def get_placeholders(self, column_names, table_names):
        # Prepare placeholders content
        columns_placeholder = " | ".join(f'"{col}"' for col in column_names)
        tables_placeholder = " | ".join(f'"{tbl}"' for tbl in table_names)
        aliases_placeholder = columns_placeholder

        return columns_placeholder, tables_placeholder, aliases_placeholder
    
    def replace_placeholders(self):
        # Replace placeholders with actual content
        table_names = self.get_table_names()
        column_names = self.get_column_names(table_names)
        columns_placeholder, tables_placeholder, aliases_placeholder = self.get_placeholders(column_names, table_names)
        self.grammar = self.grammar.replace("<columns>", columns_placeholder)
        self.grammar = self.grammar.replace("<tables>", tables_placeholder)
        self.grammar = self.grammar.replace("<aliases>", aliases_placeholder)
    
    def write_grammar(self):
        #read schema
        self.get_schema()
        #replace placeholders
        self.replace_placeholders()
        # Write the grammar to the grammar file
        with open(self.grammar_embedded, 'w') as file:
            file.write(self.grammar)

#create a llm response object
class LLMResponse:
    def __init__(self, llm_repo,llm_file, grammar_path,predicted_path):
        self.llm = Llama.from_pretrained(
    repo_id=llm_repo,
    filename=llm_file,
    verbose=False
)
        self.questions = {}
        self.answers = {}
        self.grammar = LlamaGrammar.from_file(grammar_path)
        self.predicted_path = predicted_path
        
        
    def read_questions(self,questions_file):
            #read the questions from the json file
        with open(questions_file, 'r') as file:
            json_questions = json.load(file)

        # extract db_id and question from the json file
        for question in json_questions:
            # add each db_id with all its questions to the questions dictionary
            if question['db_id'] not in self.questions:
                self.questions[question['db_id']] = []
            self.questions[question['db_id']].append(question['question'])

    def get_answers(self):
        #iterate over the questions dictionary
        for db_id, questions in self.questions.items():
            #iterate over the questions
            for question in questions:
                #get the answer for each question
                #prompt the model
                answer = self.llm(
                            question, #prompt
                            grammar=self.grammar, max_tokens=-1 # as necessary tokens
                        )
                #add the answer to the answers dictionary
                if db_id not in self.answers:
                    self.answers[db_id] = []
                self.answers[db_id].append(answer)
    
    def write_predictions(self):
        #write the answers to the output file
        #predicted sql file where each line is a predicted SQL, and interactions are seperated by one empty line
        with open(self.predicted_path, 'w') as file:
            for db_id, answers in self.answers.items():
                for answer in answers:
                    file.write(f"{answer}\n")
        
    



    

if __name__ == '__main__':
    #parse the arguments: databases folder path, questions json file path, and the output file path, and if use_embedded_grammar is set
    parser = argparse.ArgumentParser(description='Evaluate grammar')
    parser.add_argument('databases_folder', type=str, help='Folder containing the databases')
    parser.add_argument('questions_file', type=str, help='JSON file containing the questions')
    parser.add_argument('output_file', type=str, help='Output file')
    args = parser.parse_args()
    USE_EMBEDDED_GRAMMAR = args.use_embedded_grammar

