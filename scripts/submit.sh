#!/bin/bash
# FILE: Wrapper template wrapper.sh
#
#$ -cwd
#$ -j y
#$ -S /bin/bash

#$ -N MySGEJob
#$ -M lg23109@essex.ac.uk
#$ -m be
#$ -q all.q


conda activate sql
python sql_inference.py --model_id "defog/sqlcoder-7b-2" --db_path "spider/test_database" --prompt_template """### Task
Generate a SQL query to answer [QUESTION]{question}[/QUESTION]

### Database Schema
The query will run on a database with the following schema:
{schema}

### Answer
Given the database schema, here is the SQL query that [QUESTION]{question}[/QUESTION]
[SQL]
""" --questions_file "spider/test_data/dev.json" --predicted_path "predictions/T_sqlcoder-7b-2-embedded" --grammar_template_path "grammars/template.ebnf" --grammar_directory "embedded_grammars"