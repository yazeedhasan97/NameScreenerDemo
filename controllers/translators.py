import re
from transformers import MarianMTModel, MarianTokenizer
import torch


class NameTranslator:
    """
    Translates a given name between Arabic and English using Helsinki-NLP models.

    Attributes:
        model_ar_en: Model for translating Arabic to English.
        tokenizer_ar_en: Corresponding tokenizer for Arabic-to-English.
        model_en_ar: Model for translating English to Arabic.
        tokenizer_en_ar: Corresponding tokenizer for English-to-Arabic.
    """

    ARABIC_MODEL_NAME = "Helsinki-NLP/opus-mt-tc-big-ar-en"
    ENGLISH_MODEL_NAME = "Helsinki-NLP/opus-mt-tc-big-en-ar"

    def __init__(self, device: str = None):
        """
        Initialize models and tokenizers.

        Args:
            device (str): Torch device to run the models on, e.g., "cpu" or "cuda".
                          If None, uses "cuda" if available, else "cpu".
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Load Arabic-to-English model and tokenizer
        self.tokenizer_ar_en = MarianTokenizer.from_pretrained(self.ARABIC_MODEL_NAME)
        self.model_ar_en = MarianMTModel.from_pretrained(self.ARABIC_MODEL_NAME).to(self.device)

        # # Load English-to-Arabic model and tokenizer
        # self.tokenizer_en_ar = MarianTokenizer.from_pretrained(self.ENGLISH_MODEL_NAME)
        # self.model_en_ar = MarianMTModel.from_pretrained(self.ENGLISH_MODEL_NAME).to(self.device)

    def translate(self, name: str,) -> str:

        # if source_language == "ar":
        #     tokenizer = self.tokenizer_ar_en
        #     model = self.model_ar_en
        # else:
        #     tokenizer = self.tokenizer_en_ar
        #     model = self.model_en_ar

        inputs = self.tokenizer_ar_en([name], return_tensors="pt", padding=True).to(self.device)
        translated_ids = self.model_ar_en.generate(**inputs)
        translation = self.tokenizer_ar_en.decode(translated_ids[0], skip_special_tokens=True)
        return translation


if __name__ == "__main__":
    # Sample names to translate
    names = [
        "عبدالرحمن محمد المجزوب",  # Arabic name to be translated to English
        "Jakson Oscar Younes"  # English name to be translated to Arabic
    ]

    translator = NameTranslator()
    for name in names:
        translated = translator.translate(name)
        print(f"{name}  ==>  {translated}")
