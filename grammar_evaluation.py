#import necessary libraries
from llama_cpp import Llama, LlamaGrammar
import json
import argparse
import re
from tqdm import tqdm

class SQLGrammar:
    def __init__(self, grammar_path,db_path, grammar_embedded_path):
        
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
        print("Grammar saved to ", self.grammar_embedded)

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

        print("Reading questions from ", questions_file)
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
        print("NL2SQL")
        #iterate over the questions dictionary
        for db_id, questions in tqdm(self.questions.items(), desc="Answering questions"):
            #iterate over the questions
            for question in tqdm(questions, desc="Question"):
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
        print("Writing predictions to ", self.predicted_path)
        with open(self.predicted_path, 'w') as file:
            for db_id, answers in self.answers.items():
                for answer in answers:
                    file.write(f"{answer}\n")
        #save txt file
        print("Predictions saved to ", self.predicted_path)

    def predict(self, question_file):
        #read the questions from the json file
        self.read_questions(question_file)
        #get the answers for the questions
        self.get_answers()
        #write the answers to the output file
        self.write_predictions()

        
    



    

if __name__ == '__main__':
    #parse the arguments: databases folder path, questions json file path, and the output file path, and if use_embedded_grammar is set
    parser = argparse.ArgumentParser(description='Evaluate grammar')
    parser.add_argument("llm_repo", type=str, help="The repository id of the LLM model")
    parser.add_argument("llm_file", type=str, help="The file name of the LLM model")
    parser.add_argument("grammar_path", type=str, help="The path to the grammar file")
    parser.add_argument("db_path", type=str, help="The path to the database folder")
    parser.add_argument("grammar_embedded_path", type=str, help="The path to the embedded grammar file", default=None)
    parser.add_argument('questions_file', type=str, help='JSON file containing the questions')
    parser.add_argument('predicted_path', type=str, help='Output file')
    args = parser.parse_args()
    
    #create a SQLGrammar object if grammar_embedded_path is provided
    sql_grammar = SQLGrammar(args.grammar_path,args.db_path, args.grammar_embedded_path)
    #write the grammar to the embedded grammar file
    sql_grammar.write_grammar()

    #create a LLMResponse object
    llm_response = LLMResponse(args.llm_repo,args.llm_file, args.grammar_embedded_path,args.predicted_path)
    #read the questions from the json file
    llm_response.predict(args.questions_file)
    #get the answers for the questions
    


