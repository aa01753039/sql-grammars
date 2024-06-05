import re

# Read the database schema
schema = """
PRAGMA foreign_keys = ON;

CREATE TABLE "employee" (
"Employee_ID" int,
"Name" text,
"Age" int,
"City" text,
PRIMARY KEY ("Employee_ID")
);
CREATE TABLE "shop" (
"Shop_ID" int,
"Name" text,
"Location" text,
"District" text,
"Number_products" int,
"Manager_name" text,
PRIMARY KEY ("Shop_ID")
);
CREATE TABLE "hiring" (
"Shop_ID" int,
"Employee_ID" int,
"Start_from" text,
"Is_full_time" bool,
PRIMARY KEY ("Employee_ID"),
FOREIGN KEY (`Shop_ID`) REFERENCES `shop`(`Shop_ID`),
FOREIGN KEY (`Employee_ID`) REFERENCES `employee`(`Employee_ID`)
);
CREATE TABLE "evaluation" (
"Employee_ID" text,
"Year_awarded" text,
"Bonus" real,
PRIMARY KEY ("Employee_ID","Year_awarded"),
FOREIGN KEY (`Employee_ID`) REFERENCES `employee`(`Employee_ID`)
);
"""

# Extract table names
table_names = re.findall(r'CREATE TABLE "([^"]+)"', schema)

# Extract column names for each table
column_names = []
for table in table_names:
    table_schema = re.search(r'CREATE TABLE "{}" \((.*?)\);'.format(table), schema, re.DOTALL).group(1)
    columns = re.findall(r'"([^"]+)"', table_schema)
    column_names.extend(columns)

# Prepare placeholders content
columns_placeholder = " | ".join(f'"{col}"' for col in column_names)
tables_placeholder = " | ".join(f'"{tbl}"' for tbl in table_names)
aliases_placeholder = columns_placeholder  # Assuming aliases can be any column name

# Read the grammar template
with open('grammars/grammar_base.gbnf', 'r') as file:
    grammar_template = file.read()

# Replace placeholders with actual content
grammar = grammar_template.replace('COLUMN_NAMES_PLACEHOLDER', columns_placeholder)
grammar = grammar.replace('TABLE_NAMES_PLACEHOLDER', tables_placeholder)
grammar = grammar.replace('ALIAS_NAMES_PLACEHOLDER', aliases_placeholder)

# Save the populated grammar
with open('grammars/grammar_template2.gbnf', 'w') as file:
    file.write(grammar)
