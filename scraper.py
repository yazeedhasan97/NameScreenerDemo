import os
from argparse import ArgumentParser, Namespace

from controllers.scrappers import OFACDataProcessor
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

    OFAC_XML_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"

    processor = OFACDataProcessor(
        url=OFAC_XML_URL,
        connection=connection,
        factory=factory
    )

    try:
        df = processor.process()
    except Exception as error:
        print(f"Processing failed: {error}")

    factory.close()
    connection.close()


def cli() -> Namespace:
    """Configure argument parser and parse cli arguments."""

    parser = ArgumentParser(description="DataScrappersOFAC.")
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
