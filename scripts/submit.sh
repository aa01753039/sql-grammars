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
python sql_inference.py --model_id "PipableAI/pip-sql-1.3b" --db_path "spider/test_database" --prompt_template """<schema>{schema}</schema> 
<question>{question}</question>
<sql>""" --questions_file "spider/test_data/dev.json" --predicted_path "predictions/T_pip-sql-1.3b-embedded" --grammar_template_path "grammars/template.ebnf" --grammar_directory "embedded_grammars"