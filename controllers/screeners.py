import logging

# import pandas as pd
from fuzzywuzzy import fuzz

from controllers.consts import THRESHOLD
from controllers.handlers import NameHashHandler
from models.models import Customers, Sanctions


class NameScreener:
    def __init__(self, factory, connection, threshold=None, logger: logging.Logger = None):
        self._factory = factory
        self._connection = connection
        self._logger = logger if logger else logging.getLogger(__file__)
        self._threshold = threshold if threshold else THRESHOLD

    def runner(self, name, language, sep: str = ' '):
        hasher = NameHashHandler(
            language=language,
            sep=sep
        )

        code = hasher.hash(name=name)

        customers = self._factory.session.query(Customers).filter(
            Customers.hash == code
        ).all()

        sanctions = self._factory.session.query(Sanctions).filter(
            Sanctions.full_name == code
        ).all()

        matches = []
        for customer in customers:
            for sanction in sanctions:
                try:
                    similarity_score = fuzz.token_sort_ratio(customer.full_name, sanction.full_name)
                    if similarity_score >= self._threshold:
                        matches.append({
                            "customer_id": customer.id,
                            "customer_name": customer.full_name,
                            "watchlist_name": sanction.full_name,
                            "reason": sanction.reason,
                            "similarity_score": similarity_score,
                        })
                except Exception as e:
                    self._logger.info(f"Error processing customer {customer['full_name']}: {e}")
        return matches
