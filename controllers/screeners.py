import logging

# import pandas as pd
from fuzzywuzzy import fuzz
from transformers import AutoTokenizer, AutoModel

# from controllers.consts import THRESHOLD
# from models.models import Sanctions
import torch.nn.functional as F
import torch

use_auth_token = None


class NameScreener:
    def __init__(self, logger: logging.Logger = None):
        # self._factory = factory
        # self._connection = connection
        self._logger = logger if logger else logging.getLogger(__file__)
        # self._threshold = threshold if threshold else THRESHOLD

        # Initialize the Jellyfish-13B model and tokenizer once during instantiation
        # _model_name = "jellyfish-13b"
        #
        # # self._tokenizer = AutoTokenizer.from_pretrained(self._model_name, use_auth_token=use_auth_token)
        # # self._model = AutoModel.from_pretrained(self._model_name, use_auth_token=use_auth_token)
        #
        # self.translation_tokenizer = AutoTokenizer.from_pretrained(_model_name, use_auth_token=use_auth_token)
        # self.translation_model = AutoModelForSeq2SeqLM.from_pretrained(_model_name, use_auth_token=use_auth_token)

        _model_name = "NECOUDBFM/Jellyfish-13B"
        self.tokenizer = AutoTokenizer.from_pretrained(_model_name,  use_auth_token=use_auth_token)
        self.model = AutoModel.from_pretrained(_model_name, use_auth_token=use_auth_token)

    def runner(self, name, threshold=0.5, sanctions: list[str] = None,):

        sanctions = sanctions.copy() if sanctions else []

        matches = []
        for sanction in sanctions:
            try:
                similarity_score = fuzz.token_sort_ratio(name.lower(), sanction.lower())
                if similarity_score >= threshold:
                    matches.append(sanction)
            except Exception as e:
                self._logger.info(f"Error processing customer {name}: {e}")
        return matches

    def ai_runner(self, name, threshold=0.5, sanctions: list[str] = None,):

        sanctions = sanctions.copy() if sanctions else []

        # Fetch sanction names from the database
        # sanctions = self._connection.select(
        #     """select concat("firstName", ' ', "lastName") from screening.ofac_sdn """
        # ).tolist()

        matches = []
        for sanction in sanctions:
            try:
                # Tokenize the input name and the sanction entity
                inputs = self.tokenizer([name, sanction], return_tensors="pt", padding=True, truncation=True)
                # Generate embeddings using mean pooling over token embeddings
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    embeddings = outputs.last_hidden_state.mean(dim=1)
                # Compute cosine similarity between the two embeddings
                similarity_score = F.cosine_similarity(
                    embeddings[0].unsqueeze(0), embeddings[1].unsqueeze(0)
                ).item()
                # Check if the similarity exceeds the threshold
                if similarity_score >= threshold:
                    matches.append(sanction)
            except Exception as e:
                self._logger.info(f"Error processing customer {name}: {e}")
        return matches
