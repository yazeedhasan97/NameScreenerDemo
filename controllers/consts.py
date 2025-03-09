
from enum import Enum

# Constants
OFAC_API_URL = "https://api.treasury.gov/ofac/sanctions/list"
THRESHOLD = 80  # Fuzzy matching threshold
API_KEY = "your_ofac_api_key_here"


ALL = "ALL"

class RecoType(Enum):
    ENTITY = 1
    INDIVIDUAL = 2

class SupportedLanguage(Enum):
    ARABIC = 'ar'
    ENGLISH = 'en'
