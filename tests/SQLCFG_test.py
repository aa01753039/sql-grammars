import argparse
from pathlib import Path


from core.SQLCFG import SQLCFG

if __name__ == "__main__":
    # parse the arguments: databases folder path, questions json file path, and the output file path, and if use_embedded_grammar is set
    parser = argparse.ArgumentParser(description="Evaluate grammar")
    
    parser.add_argument(
        "--grammar_template_path",
        type=str,
        help="The path to the grammar file",
        default=None,
        required=False,
    )
    parser.add_argument(
        "--db_path",
        type=str,
        help="The path to the database folder",
        default=None,
        required=False,
    )
    parser.add_argument(
        "--grammar_directory",
        type=str,
        help="The path to the embedded grammar directory",
        default=None,
        required=False,
    )

    
    args = parser.parse_args()



    grammar_path = None
    # create a SQLGrammar object if grammar_directory is provided
    if args.grammar_directory:
        print("Creating SQLGrammar object")
        # create args.grammar_directory if it it does not exist
        if not Path(args.grammar_directory).exists():
            Path(args.grammar_directory).mkdir(parents=True, exist_ok=True)

        if Path(args.grammar_directory).is_dir():
            sql_grammar = SQLCFG(
                args.grammar_template_path, args.db_path, args.grammar_directory
            )
            # write the grammar to the embedded grammar file
            sql_grammar.process_databases()
            grammar_path = args.grammar_directory
    
