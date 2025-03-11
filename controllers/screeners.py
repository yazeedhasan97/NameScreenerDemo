import logging

# import pandas as pd
from fuzzywuzzy import fuzz
from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification

# from controllers.consts import THRESHOLD
# from models.models import Sanctions
import torch.nn.functional as F
import torch
from torch.nn.functional import softmax

from models.models import Sanctions

use_auth_token = None


class NameScreener:
    # _model_name = "NECOUDBFM/Jellyfish-13B"
    _model_name = "Launchpad/ditto"

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

        self.tokenizer = AutoTokenizer.from_pretrained(
            self._model_name, use_auth_token=use_auth_token,
            # timeout=60,  # Increase timeout to 60 seconds
            # resume_download=True,  # Resume failed downloads instead of restarting
        )
        # tokenizer = AutoTokenizer.from_pretrained(model_name)

        # for the jelly fish model
        # if self.tokenizer.pad_token is None:
        #     self.tokenizer.pad_token = self.tokenizer.eos_token
        #
        # if self.tokenizer.eos_token is None:
        #     self.tokenizer.add_special_tokens({'pad_token': '[PAD]'})

        # self.model = AutoModel.from_pretrained(
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self._model_name, use_auth_token=use_auth_token,
            trust_remote_code=True,
            # timeout=60,  # Increase timeout to 60 seconds
            # resume_download=True,  # Resume failed downloads instead of restarting
        )

    def runner(self, name, threshold=0.5, sanctions: list[str] = None, ):

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

    def jelly_fish_runner(self, name, threshold=0.5, sanctions: list[Sanctions] = None, ):

        sanctions = sanctions.copy() if sanctions else []

        # Fetch sanction names from the database
        # sanctions = self._connection.select(
        #     """select concat("firstName", ' ', "lastName") from screening.ofac_sdn """
        # ).tolist()

        matches = []
        for idx, sanction in enumerate(sanctions):
            self._logger.info("-" * 100)
            self._logger.info(f"Processing {idx} reco")

            try:
                # Tokenize the input name and the sanction entity
                if not isinstance(sanction.first_name, str) and not isinstance(sanction.last_name, str):
                    self._logger.warning(f"Invalid sanction name: {sanction}")
                    continue

                sanc_name = f"{sanction.first_name} {sanction.last_name}"

                inputs = self.tokenizer(
                    [name.lower(), sanc_name.lower()],
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    # max_length=self.tokenizer.model_max_length if self.tokenizer.model_max_length else 128
                    max_length=512
                )
                self._logger.info(f"Tokenized inputs for {name}: {inputs}")
                inputs = {key: value.to(torch.int32) for key, value in inputs.items()}
                self._logger.info(f"Tokenized inputs for {name}: {inputs}")
                # Generate embeddings using mean pooling over token embeddings
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    embeddings = outputs.last_hidden_state.mean(dim=1)
                # Compute cosine similarity between the two embeddings
                similarity_score = F.cosine_similarity(
                    embeddings[0].unsqueeze(0), embeddings[1].unsqueeze(0)
                ).clamp(min=-1.0, max=1.0).item()
                # Check if the similarity exceeds the threshold
                self._logger.info(f"{name} -- {sanc_name} || {similarity_score}/{threshold}", )
                if similarity_score >= threshold:
                    matches.append([sanc_name, similarity_score, sanction.uid])
            except Exception as e:
                self._logger.info(f"Error processing customer {name}: {e}")
        return matches

    def ditto_runner(self, name: str, threshold=0.5, sanctions: list[Sanctions] = None, ):

        # Load tokenizer and model
        # tokenizer = AutoTokenizer.from_pretrained(model_name)
        # model = AutoModelForSequenceClassification.from_pretrained(model_name)
        matches = []
        for idx, sanction in enumerate(sanctions):
            self._logger.info("-" * 100)
            self._logger.info(f"Processing {idx} reco")
            sanc_name = f"{sanction.first_name} {sanction.last_name}"
            # Tokenize the input pair
            inputs = self.tokenizer(name, sanc_name, return_tensors="pt", truncation=True)

            # Run inference
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                # Calculate probability for class 1 (match)
                probabilities = softmax(logits, dim=1)
                similarity_score = probabilities[0, 1].item()

            if similarity_score >= threshold:
                matches.append([sanc_name, similarity_score, sanction.uid])

        return matches
