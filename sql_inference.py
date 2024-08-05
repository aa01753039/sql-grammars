import argparse
from pathlib import Path

from core.Text2SQL import Text2SQL
from core.SQLCFG import SQLCFG

if __name__ == "__main__":
    # parse the arguments: databases folder path, questions json file path, and the output file path, and if use_embedded_grammar is set
    parser = argparse.ArgumentParser(description="Evaluate grammar")
    parser.add_argument(
        "--model_id",
        type=str,
        help="The hugging face repository id of the LLM model",
    )
    
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

    parser.add_argument(
        "--prompt_template",
        type=str,
        help="The string prompt template",
        default=None,
        required=False,
    )

    parser.add_argument(
        "--questions_file",
        type=str,
        help="JSON file containing the questions",
    )
    parser.add_argument(
        "--predicted_path",
        type=str,
        help="Output directory for the predictions ",
    )

    args = parser.parse_args()

    print(args)

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
    else:
        if args.grammar_template_path:
            grammar_path = args.grammar_template_path

    # create a LLMResponse object
    llm_response = Text2SQL(
        args.model_id,
        args.predicted_path,
        grammar_path,
        args.db_path,
        args.prompt_template,
    )
    # read the questions from the json file
    llm_response.predict(args.questions_file)
    # convert the JSON file to a TXT file
    llm_response.convert_json_to_txt()