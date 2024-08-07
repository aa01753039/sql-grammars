#!/bin/bash
# FILE: Wrapper template wrapper.sh
#
#$ -cwd
#$ -j y
#$ -S /bin/bash

#$ -N T_SC_Llama-3.1-8B-Instruct-embedded
#$ -M lg23109@essex.ac.uk
#$ -m be
#$ -q all.q
#$ -l mem_free=256G

conda activate sql
python sql_inference.py --model_id "meta-llama/Meta-Llama-3.1-8B-Instruct" --db_path "spider/test_database" --prompt_template """
The problem is given below in natural language.
Additionally, here are the CREATE TABLE statements for the schema:
{schema}

Do not write anything after the SQL query.
Do not write anything other than the SQL query - no comments, no newlines, no print statements.

Problem: {question}

""" --questions_file "spider/test_data/dev.json" --predicted_path "predictions/T_SC_Llama-3.1-8B-Instruct-embedded" --grammar_template "grammars/template.ebnf" --grammar_directory "embedded_grammars3"