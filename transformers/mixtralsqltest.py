import torch
from transformers import AutoTokenizer, BitsAndBytesConfig, GenerationConfig
from transformers.models.mixtral import MixtralForCausalLM
from transformers_cfg.grammar_utils import IncrementalGrammarConstraint
from transformers_cfg.generation.logits_process import GrammarConstrainedLogitsProcessor
import resource, sys

resource.setrlimit(resource.RLIMIT_STACK, (2**29, -1))

sys.setrecursionlimit(10**4)

PROMPT = """
   [INST] You are a natural language to SQL translator.
For the given schema, output the SQL query you need to answer the problem.

The problem is given below in natural language.
If part of the problem can not be accomplished using SQL queries, for example visualization requests,
only output the most meaningful sql query that returns the data required for the problem. 
Additionally, here are the CREATE TABLE statements for the schema:
{create_tables}

Do not include the CREATE TABLE statements in the SQL query. Do not write anything after the SQL query.
Do not write anything other than the SQL query - no comments, no newlines, no print statements.  

Problem: {problem}
[/INST]
   """

MIMIC_III_TABLES = """
CREATE TABLE PATIENTS 
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL UNIQUE,
   GENDER VARCHAR(5) NOT NULL,
   DOB TIMESTAMP(0) NOT NULL,
   DOD TIMESTAMP(0)
);

CREATE TABLE ADMISSIONS
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL UNIQUE,
   ADMITTIME TIMESTAMP(0) NOT NULL,
   DISCHTIME TIMESTAMP(0),
   ADMISSION_TYPE VARCHAR(50) NOT NULL,
   ADMISSION_LOCATION VARCHAR(50) NOT NULL,
   DISCHARGE_LOCATION VARCHAR(50),
   INSURANCE VARCHAR(255) NOT NULL,
   LANGUAGE VARCHAR(10),
   MARITAL_STATUS VARCHAR(50),
   ETHNICITY VARCHAR(200) NOT NULL,
   AGE INT NOT NULL,
   FOREIGN KEY(SUBJECT_ID) REFERENCES PATIENTS(SUBJECT_ID)
);

CREATE TABLE D_ICD_DIAGNOSES
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   ICD9_CODE VARCHAR(10) NOT NULL UNIQUE,
   SHORT_TITLE VARCHAR(50) NOT NULL,
   LONG_TITLE VARCHAR(255) NOT NULL
);

CREATE TABLE D_ICD_PROCEDURES 
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   ICD9_CODE VARCHAR(10) NOT NULL UNIQUE,
   SHORT_TITLE VARCHAR(50) NOT NULL,
   LONG_TITLE VARCHAR(255) NOT NULL
);

CREATE TABLE D_LABITEMS 
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   ITEMID INT NOT NULL UNIQUE,
   LABEL VARCHAR(200) NOT NULL
);

CREATE TABLE D_ITEMS 
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   ITEMID INT NOT NULL UNIQUE,
   LABEL VARCHAR(200) NOT NULL,
   LINKSTO VARCHAR(50) NOT NULL
);

CREATE TABLE DIAGNOSES_ICD
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   ICD9_CODE VARCHAR(10) NOT NULL,
   CHARTTIME TIMESTAMP(0) NOT NULL,
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID),
   FOREIGN KEY(ICD9_CODE) REFERENCES D_ICD_DIAGNOSES(ICD9_CODE)
);

CREATE TABLE PROCEDURES_ICD
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   ICD9_CODE VARCHAR(10) NOT NULL,
   CHARTTIME TIMESTAMP(0) NOT NULL,
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID),
   FOREIGN KEY(ICD9_CODE) REFERENCES D_ICD_PROCEDURES(ICD9_CODE)
);

CREATE TABLE LABEVENTS
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   ITEMID INT NOT NULL,
   CHARTTIME TIMESTAMP(0),
   VALUENUM DOUBLE PRECISION,
   VALUEUOM VARCHAR(20),
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID),
   FOREIGN KEY(ITEMID) REFERENCES D_LABITEMS(ITEMID)
);

CREATE TABLE PRESCRIPTIONS
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   STARTDATE TIMESTAMP(0) NOT NULL,
   ENDDATE TIMESTAMP(0),
   DRUG VARCHAR(100) NOT NULL,
   DOSE_VAL_RX VARCHAR(120) NOT NULL,
   DOSE_UNIT_RX VARCHAR(120) NOT NULL,
   ROUTE VARCHAR(120) NOT NULL,
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID)
);

CREATE TABLE COST
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   EVENT_TYPE VARCHAR(20) NOT NULL,
   EVENT_ID INT NOT NULL,
   CHARGETIME TIMESTAMP(0) NOT NULL,
   COST DOUBLE PRECISION NOT NULL,
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID),
   FOREIGN KEY(EVENT_ID) REFERENCES DIAGNOSES_ICD(ROW_ID),
   FOREIGN KEY(EVENT_ID) REFERENCES PROCEDURES_ICD(ROW_ID),
   FOREIGN KEY(EVENT_ID) REFERENCES LABEVENTS(ROW_ID),
   FOREIGN KEY(EVENT_ID) REFERENCES PRESCRIPTIONS(ROW_ID)  
);

CREATE TABLE CHARTEVENTS
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   ICUSTAY_ID INT NOT NULL,
   ITEMID INT NOT NULL,
   CHARTTIME TIMESTAMP(0) NOT NULL,
   VALUENUM DOUBLE PRECISION,
   VALUEUOM VARCHAR(50),
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID),
   FOREIGN KEY(ICUSTAY_ID) REFERENCES ICUSTAYS(ICUSTAY_ID),
   FOREIGN KEY(ITEMID) REFERENCES D_ITEMS(ITEMID)
);

CREATE TABLE INPUTEVENTS_CV
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   ICUSTAY_ID INT NOT NULL,
   CHARTTIME TIMESTAMP(0) NOT NULL,
   ITEMID INT NOT NULL,
   AMOUNT DOUBLE PRECISION,
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID),
   FOREIGN KEY(ICUSTAY_ID) REFERENCES ICUSTAYS(ICUSTAY_ID),
   FOREIGN KEY(ITEMID) REFERENCES D_ITEMS(ITEMID)
);

CREATE TABLE OUTPUTEVENTS
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   ICUSTAY_ID INT NOT NULL,
   CHARTTIME TIMESTAMP(0) NOT NULL,
   ITEMID INT NOT NULL,
   VALUE DOUBLE PRECISION,
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID),
   FOREIGN KEY(ICUSTAY_ID) REFERENCES ICUSTAYS(ICUSTAY_ID),
   FOREIGN KEY(ITEMID) REFERENCES D_ITEMS(ITEMID)
);

CREATE TABLE MICROBIOLOGYEVENTS
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   CHARTTIME TIMESTAMP(0) NOT NULL,
   SPEC_TYPE_DESC VARCHAR(100),
   ORG_NAME VARCHAR(100),
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID)
);

CREATE TABLE ICUSTAYS
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   ICUSTAY_ID INT NOT NULL,    
   FIRST_CAREUNIT VARCHAR(20) NOT NULL,
   LAST_CAREUNIT VARCHAR(20) NOT NULL,
   FIRST_WARDID SMALLINT NOT NULL,
   LAST_WARDID SMALLINT NOT NULL,    
   INTIME TIMESTAMP(0) NOT NULL,
   OUTTIME TIMESTAMP(0),
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID)
);

CREATE TABLE TRANSFERS
(
   ROW_ID INT NOT NULL PRIMARY KEY,
   SUBJECT_ID INT NOT NULL,
   HADM_ID INT NOT NULL,
   ICUSTAY_ID INT,
   EVENTTYPE VARCHAR(20) NOT NULL,
   CAREUNIT VARCHAR(20),
   WARDID SMALLINT,
   INTIME TIMESTAMP(0) NOT NULL,
   OUTTIME TIMESTAMP(0),
   FOREIGN KEY(HADM_ID) REFERENCES ADMISSIONS(HADM_ID)
);
"""


def generate_one(
   model,
   tokenizer,
   processors,
   question: str,
   identifier: str,
   device="cpu",
):
   gen_config = GenerationConfig(**(model.generation_config.to_dict()))
   prompt = PROMPT.format(
       create_tables=MIMIC_III_TABLES,
       problem=question,
   )
   input_ids = tokenizer(
       [prompt], add_special_tokens=False, return_tensors="pt", padding=True
   )["input_ids"].to(device)
   output = model.generate(
       input_ids,
       max_new_tokens=200,
       logits_processor=processors,
       num_return_sequences=1,
       generation_config=gen_config,
   )
   return {identifier: tokenizer.batch_decode(output, skip_special_tokens=True)[0]}


if __name__ == "__main__":
   # Detect if GPU is available, otherwise use CPU
   device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
   print(f"Using device: {device}")

   model_id = "mistralai/Mixtral-8x7B-Instruct-v0.1"
   quantization_config = BitsAndBytesConfig(
       load_in_4bit=True,
       bnb_4bit_quant_type="nf4",
       bnb_4bit_compute_dtype="float16",
   )
   model = MixtralForCausalLM.from_pretrained(
       model_id, quantization_config=quantization_config, device_map="auto"
   )

   # Load model and tokenizer
   tokenizer = AutoTokenizer.from_pretrained(model_id)
   tokenizer.pad_token = tokenizer.eos_token
   model.generation_config.pad_token_id = model.generation_config.eos_token_id

   # Load sql grammar
   with open("sql_query.ebnf", "r") as file:
       grammar_str = file.read()
   grammar = IncrementalGrammarConstraint(grammar_str, "root", tokenizer)
   grammar_processor = GrammarConstrainedLogitsProcessor(grammar)

   # Generate
   question = "what is lidocaine 5% ointment's way of ingesting it?"

   generate_one(
       model,
       tokenizer,
       [grammar_processor],
       question,
       "qid",
       device=model.device,
   )