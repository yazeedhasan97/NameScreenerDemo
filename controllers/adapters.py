from functools import lru_cache
from hashlib import sha256


class OFACAdapter:

    # def update(self):
    #     # Fetch sanctions list from OFAC API
    #     ofac_adapter = OFACAdapter(OFAC_API_URL, api_key)
    #     sanctions_list = ofac_adapter.fetch_sanctions_list()

    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key

    @lru_cache(maxsize=100)  # Cache sanctions list to reduce API calls
    def fetch_sanctions_list(self, requests=None):
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(self.api_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            sanctions_list = []
            for entry in data.get("results", []):
                full_name = entry.get("name", "")
                names = full_name.split()
                name_count = len(names)
                name_hash = self.generate_name_hash(names)
                sanctions_list.append({
                    "full_name": full_name,
                    "name_1": names[0] if name_count > 0 else "",
                    "name_2": names[1] if name_count > 1 else "",
                    "name_3": names[2] if name_count > 2 else "",
                    "name_count": name_count,
                    "name_hash": name_hash,
                    "reason": entry.get("reason", "Sanctioned Entity"),
                })
            return sanctions_list
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from OFAC API: {e}")
            return []

    @staticmethod
    def generate_name_hash(names):
        """Generate a hash based on the number of names and the first letter of each name."""
        hash_input = f"{len(names)}:{':'.join(name[0] for name in names)}"
        return sha256(hash_input.encode()).hexdigest()
