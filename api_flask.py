import logging
import os
from enum import Enum

from controllers.consts import RecoType, SupportedLanguage
from controllers.handlers import NameHandler
from controllers.screeners import NameScreener
from controllers.translators import NameTranslator
from models.db import get_db_hook
from models.models import Sanctions
from utilities.loggings import MultipurposeLogger

from flask import Flask, request, jsonify
from argparse import ArgumentParser, Namespace

from utilities.utils import load_json_file


class APIService:
    """Flask API Service for processing names."""

    def __init__(self, factory, logger: MultipurposeLogger):
        self.app = Flask(__name__)
        self._factory = factory
        self._logger = logger if logger else logging.getLogger(__file__)
        self._screener = NameScreener()
        self._translator = NameTranslator()
        self._setup_routes()

    def _validate_parameters(self, type, name, threshold):
        # Validate parameters
        if type.upper() not in [rt.name for rt in RecoType]:
            return jsonify({"error": "Invalid type"}), 400
        if not isinstance(name, str) or not name.strip():
            return jsonify({"error": "Invalid name"}), 400
        if not (isinstance(threshold, (int, float)) and (0 <= threshold <= 1 or 1 <= threshold <= 100)):
            return jsonify({"error": "Invalid threshold"}), 400

        return True

    def _setup_routes(self):
        """Defines API routes."""

        @self.app.route('/process', methods=['POST'])
        def process():
            data = request.json
            type = data.get("type")
            name = data.get("name")
            threshold = data.get("threshold")

            processed = self._validate_parameters(type, name, threshold)
            if not processed:
                return processed

            name_handler = NameHandler()
            # Process name
            language = name_handler.detect_language(name)
            # if language not in [rt.value for rt in SupportedLanguage]:
            #     return jsonify({"error": f"Unsupported Language: {language}"}), 400

            if language == 'ar':
                name = self._translator.translate(name)

            search_hash = name_handler.hash(
                name=name,
                type=type,
                # language=language
            )

            sanctions = self._factory.session.query(Sanctions).filter(
                Sanctions.search_hash == str(search_hash)
            ).all()

            matches = self._screener.ai_runner(
                name=name,
                sanctions=sanctions
            )

            return jsonify({
                "name": name,
                "language": language,
                "hash": hash,
                "matches": matches
            })

    def run(self):
        """Starts the Flask API server."""
        self.app.run(debug=True)


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
    return parser.parse_args()


def main():
    config = load_json_file(args.config)
    logger.info(f"Loaded Config: {config}")

    logger.info(f"Initiating DB connection.")
    connection, factory = get_db_hook(
        config=config.get("database", ),
        logger=logger,
        # create=True
    )
    api_service = APIService(factory=factory, logger=logger)
    api_service.run()

    factory.close()
    connection.close()


if __name__ == "__main__":
    args = cli()

    # Initialize Logger
    logger = MultipurposeLogger(name='NameScreening', path=args.log, create=True)

    # Validate Config File
    if not os.path.exists(args.config) or not os.path.isfile(args.config) or not args.config.endswith('.json'):
        logger.error("Error: Provided Config path is invalid.")
        raise ValueError("Provided Config path is invalid.")

    # Start API Service

    main()
