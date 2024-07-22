import argparse
from pathlib import Path

from core.LLMResponser import LLMResponser
from core.SQLGrammar import SQLGrammar

if __name__ == "__main__":
    # parse the arguments: databases folder path, questions json file path, and the output file path, and if use_embedded_grammar is set
    parser = argparse.ArgumentParser(description="Evaluate grammar")
    parser.add_argument(
        "--llm_repo",
        type=str,
        help="The repository id of the LLM model",
    )
    parser.add_argument(
        "--llm_file",
        type=str,
        help="The file name of the LLM model",
    )
    parser.add_argument(
        "--grammar_template_path",
        type=str,
        help="The path to the grammar file",
        default=None,
        required=False,
    )
    parser.add_argument(
        "--db_base_path",
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

    grammar_path = None
    # create a SQLGrammar object if grammar_directory is provided
    if args.grammar_directory:
        print("Creating SQLGrammar object")
        # create args.grammar_directory if it it does not exist
        if not Path(args.grammar_directory).exists():
            Path(args.grammar_directory).mkdir(parents=True, exist_ok=True)

        if Path(args.grammar_directory).is_dir():
            sql_grammar = SQLGrammar(
                args.grammar_template_path, args.db_base_path, args.grammar_directory
            )
            print(sql_grammar)
            # write the grammar to the embedded grammar file
            sql_grammar.process_databases()
            grammar_path = args.grammar_directory
    else:
        if args.grammar_template_path:
            grammar_path = args.grammar_template_path

    # create a LLMResponse object
    llm_response = LLMResponser(
        args.llm_repo,
        args.llm_file,
        args.predicted_path,
        grammar_path,
        args.db_base_path,
        args.prompt_template,
    )
    # read the questions from the json file
    llm_response.predict(args.questions_file)
    # convert the JSON file to a TXT file
    llm_response.convert_json_to_txt()