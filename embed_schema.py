import sqlite3

def get_db_schema(db_path):
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    
    # Get table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    schema = {}
    for table in tables:
        table_name = table[0]
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        schema[table_name] = [column[1] for column in columns]  # column[1] is the column name

    connection.close()
    return schema

def generate_gbnf_with_schema(schema):
    schema_names = "schema-name ::= " + " | ".join([f'"{schema_name}"' for schema_name in schema.keys()]) + "\n"
    
    table_names = "table-name ::= " + " | ".join([f'"{table}"' for table in schema.keys()]) + "\n"
    column_rules = ""
    for table, columns in schema.items():
        column_rules += " | ".join([f'"{column}"' for column in columns]) 
    
    column_names = '(schema-name ".")? (table-name ".")? (' + column_rules + ' | quoted-identifier)'

    gbnf = f"""
# Root rule for a SELECT statement, including subqueries within FROM and WHERE clauses
root ::= select-statement [;]?

# SELECT statement with optional distinct, columns, FROM clause, WHERE clause, JOINs, GROUP BY, ORDER BY, and LIMIT
select-statement ::= "SELECT " distinct? columns from-clause? where-clause? join-clause* group-by-clause? order-by-clause? limit-clause?

# Optional DISTINCT keyword
distinct ::= "DISTINCT "?

# Columns to select, either all (*) or a comma-separated list of column names or functions
columns ::= "*" | column-or-function (", " column-or-function)*

# Column or function
column-or-function ::= (column | function alias?)

# Individual column name
column ::= {column_names}
{schema_names}
{table_names}

# Function call, simplified to no arguments or single argument
function ::= [a-zA-Z_][a-zA-Z0-9_]* "(" (column | "*" | ) ")"

# FROM clause specifying the table(s) or subquery to select from
from-clause ::= ws? "FROM " (tables | subquery) (ws table-alias)?

# Tables, either a single table, a subquery as a table, or a comma-separated list of table names
tables ::= table (", " table)*

# Individual table name or subquery as table
table ::= [a-zA-Z_][a-zA-Z0-9_]* | "(" select-statement ")" | quoted-identifier

# Alias for a table or subquery, simplified
alias ::= ws? ("AS " | "as ")? [a-zA-Z][a-zA-Z0-9_]*
table-alias ::= ws? ("AS " | "as ")? [a-zA-Z]

# WHERE clause with a condition, including subquery conditions
where-clause ::= ws? "WHERE " condition

# JOIN clause, simplified to INNER JOIN
join-clause ::= ws? "JOIN " table (ws alias)? " ON " condition

# Condition, allowing column comparisons, IN, EXISTS, and subquery conditions
condition ::= (
        column ws? comparator ws? (value | column)
        | column " IN (" select-statement ")"
        | "EXISTS (" select-statement ")"
    )

# Comparator, basic options
comparator ::= "=" | "<>" | "<" | ">" | "<=" | ">="

# Value, numeric, quoted string, or subquery
value ::= number | quoted-string | "(" select-statement ")"

# Subquery structure
subquery ::= "(" select-statement ")"

# Numeric value, integer or float for simplicity
number ::= "-"? [0-9]+ ("." [0-9]+)?

# Quoted string, simplifying to anything between single quotes
quoted-string ::= "'" [^']* "'"

# GROUP BY clause, specifying columns for grouping
group-by-clause ::= ws? "GROUP BY " group-columns

# Grouping columns, either a single column or a comma-separated list
group-columns ::= column (", " column)*

# ORDER BY clause, specifying column sorting
order-by-clause ::= ws? "ORDER BY " order-columns

# Ordering columns, either a single column or a comma-separated list, with optional direction
order-columns ::= order-column (", " order-column)*

# Order by a single column, optionally with ASC or DESC
order-column ::= column (" ASC" | " DESC")?

# LIMIT clause, to limit the number of results, with optional OFFSET
limit-clause ::= ws? "LIMIT " number (" OFFSET " number)?

# Quoted identifier for cases where identifiers include spaces or other special characters
quoted-identifier ::= ["] [^"]* ["]

# Optional whitespace, for better readability in the grammar
ws ::= [ \t\n]*
"""
    return gbnf

# Usage example
db_path = 'spider/database/employee_hire_evaluation/employee_hire_evaluation.sqlite'
schema = get_db_schema(db_path)
gbnf = generate_gbnf_with_schema(schema)
#save as a file the gbnf
with open('grammars/grammar_embeded.gbnf', 'w') as file:
    file.write(gbnf)

