#!/bin/bash
# FILE: Wrapper template wrapper.sh
#
#$ -cwd
#$ -j y
#$ -S /bin/bash

#$ -N Test_Databases
#$ -M lg23109@essex.ac.uk
#$ -m be
#$ -q all.q

python test_databases.py "spider/test_database"