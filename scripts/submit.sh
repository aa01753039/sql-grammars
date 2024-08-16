#!/bin/bash
# FILE: Wrapper template wrapper.sh
#
#$ -cwd
#$ -j y
#$ -S /bin/bash

#$ -N T_SC_Llama-3.1-8B
#$ -M lg23109@essex.ac.uk
#$ -m be
#$ -q all.q
#$ -l mem_free=64G
source /usr/local/gpuallocation.sh

conda activate sql

python sql_inference.py --model_id "meta-llama/Meta-Llama-3.1-8B" --db_path "spider/test_database" --prompt_template """Your role is a natural language to SQL translator who is an expert in writing SQL queries in SQLite dialect.
For the given schema, output the SQL query you need to answer the problem.

The problem is given below in natural language.
Additionally, here are the CREATE TABLE statements for the schema:
{schema}

Do not write anything after the SQL query.
Do not write anything other than the SQL query - no comments, no newlines, no print statements.

Problem: {question}

""" --questions_file "spider/test_data/dev_sample.json" --predicted_path "predictions/test_T_SC_Llama-3.1-8B"