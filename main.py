import os
from argparse import ArgumentParser, Namespace


# from controllers.screeners import NameScreener
# from controllers.translators import NameTranslator
from models.db import get_db_hook
from utilities.loggings import MultipurposeLogger
from utilities.utils import load_json_file


def main():
    config = load_json_file(args.config)
    logger.info(f"Loaded Config: {config}")

    logger.info(f"Initiating DB connection.")
    connection, factory = get_db_hook(
        config=config.get("database", ),
        logger=logger,
        create=True
    )

    # screener = NameScreener(
    #     logger=logger,
    #     factory=factory,
    #     connection=connection
    # )
    #
    # translator = NameTranslator()
    #
    # lst = []
    # for name in args.customers:
    #     translated_name = translator.translate(name)
    #     # lst.extend(screener.runner(
    #     #     name=translated_name,
    #     #     language=args.language
    #     # ))
    #     print("-" * 50)
    #     print(f"Translated Name: {translated_name}")
    #     print("-" * 50)
    #
    #     lst.extend(screener.ai_runner(
    #         name=translated_name,
    #     ))
    #
    # if lst:
    #     print("Potential Matches Found:")
    #     print(lst)
    # else:
    #     print("No matches found.")

    factory.close()
    connection.close()


def cli() -> Namespace:
    """Configure argument parser and parse cli arguments."""

    parser = ArgumentParser(description="FinTech Name Screener Locator.")
    parser.add_argument(
        "--config",
        required=True,
        type=str,
        help="The path to the config .json file.",
    )
    parser.add_argument(
        "--log",
        type=str,
        default='logs',
        help="The path to the generated logs directory.",
    )
    # parser.add_argument(
    #     "--language",
    #     type=Language,
    #     default=Language.ENGLISH,
    #     help="Screen the name based on this language.",
    # )
    parser.add_argument(
        "--customers",
        type=str,
        nargs='+',
        help="The run_for date in the format YYYYMMDD.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = cli()

    logger = MultipurposeLogger(
        name='NameScreening', path=args.log,
        create=True
    )

    if not os.path.exists(args.config) or not os.path.isfile(args.config) or not args.config.endswith('.json'):
        logger.error("Error: Provided Config path 1- Not exists or,\n2- Not a file or,\n3- Not JSON file.")
        raise ValueError("Provided Config path 1- Not exists or,\n2- Not a file or,\n3- Not JSON file.")

    main()
