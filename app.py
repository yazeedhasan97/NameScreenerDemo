import logging
import os
# from enum import Enum
from flask import Flask, request, jsonify

from controllers.consts import RecoType
from controllers.handlers import NameHandler
from controllers.screeners import NameScreener
from controllers.translators import NameTranslator
from models.db import get_db_hook
from models.models import Sanctions
from utilities.loggings import MultipurposeLogger
from utilities.utils import load_json_file


class APIService:
    """Flask API Service for processing names."""

    def __init__(self, factory, logger: MultipurposeLogger = None):
        self.app = Flask(__name__)
        self._factory = factory
        self._logger = logger if logger else logging.getLogger(__file__)
        self._screener = NameScreener()
        self._translator = NameTranslator()
        self._setup_routes()

    def _validate_parameters(self, type, name, threshold):
        """Validates API parameters."""
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
            language = name_handler.detect_language(name)

            if language == 'ar':
                name = self._translator.translate(name)

            search_hash = name_handler.hash(name=name, type=type)

            sanctions = self._factory.session.query(Sanctions).filter(
                Sanctions.search_hash == str(search_hash)
            ).all()

            matches = self._screener.ai_runner(name=name, sanctions=sanctions)

            return jsonify({
                "name": name,
                "language": language,
                "hash": search_hash,
                "matches": matches
            })

    def run(self):
        """Starts the Flask API server."""
        self.app.run(host="0.0.0.0", port=5000)


def main():
    """Main function to start the Flask API with DB connection."""
    # Load config from environment variable
    config_path = os.getenv("SCREENING_CONFIG_PATH", None)
    if not config_path or not os.path.exists(config_path) or not config_path.endswith('.json'):
        raise ValueError("Error: SCREENING_CONFIG_PATH is not set or is invalid.")

    config = load_json_file(config_path)
    # logger.info(f"Loaded Config: {config}")

    # Initialize DB Connection
    # logger.info(f"Initiating DB connection.")
    connection, factory = get_db_hook(config=config.get("database"), )

    # Start API Service
    api_service = APIService(factory=factory, )
    api_service.run()

    # Close DB Connection
    factory.close()
    connection.close()


if __name__ == "__main__":
    # Initialize Logger
    # logger = MultipurposeLogger(name='NameScreening', path='logs', create=True)

    # Start API Service
    main()
