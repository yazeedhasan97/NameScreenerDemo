import os
import requests
import xml.etree.ElementTree as ET
import pandas as pd

from controllers.consts import SupportedLanguage, RecoType
from models.models import SCHEMA, Sanctions


class OFACDataProcessor:
    """
    A class to download, parse, and store OFAC sanctions XML data.

    Attributes:
        url (str): URL to download the XML file.
        xml_file (str): Local filename to store the downloaded XML.
    """

    def __init__(self, url, xml_file="sdn.xml", connection=None, factory=None):
        """
        Initialize the OFACDataProcessor with download and storage parameters.
        """
        self.url = url
        self.xml_file = xml_file
        self.connection = connection
        self.factory = factory

    def download_xml(self, timeout=300):
        """
        Download the XML file from the specified URL and save it locally.
        Raises:
            requests.RequestException: If an error occurs during the download.
        """
        try:
            response = requests.get(self.url, stream=True, timeout=timeout)
            response.raise_for_status()
            with open(self.xml_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        f.write(chunk)
            print(f"Downloaded XML file to '{self.xml_file}'.")
        except requests.RequestException as e:
            print(f"Error downloading XML: {e}")
            raise
        except Exception as e:
            print(f"Error downloading XML: {e}")
            raise

    @staticmethod
    def flatten_element(elem, parent_key=""):
        """
        Recursively flattens an XML element into a dictionary.
        If an element has multiple children with the same tag,
        their texts are concatenated using "; ".
        Args:
            elem (xml.etree.ElementTree.Element): The XML element to flatten.
            parent_key (str): The prefix for the key names.
        Returns:
            dict: A dictionary of flattened XML element data.
        """
        items = {}
        for child in elem:
            # Remove namespace if present
            tag = child.tag.split('}')[-1]
            new_key = f"{parent_key}.{tag}" if parent_key else tag
            if len(child):
                child_items = OFACDataProcessor.flatten_element(child, new_key)
                for k, v in child_items.items():
                    if k in items:
                        items[k] += "; " + v
                    else:
                        items[k] = v
            else:
                text = child.text.strip() if child.text else ""
                if new_key in items:
                    items[new_key] += "; " + text
                else:
                    items[new_key] = text
        return items

    def parse_xml_to_dataframe(self):
        """
        Parse the full XML file and convert its records to a pandas DataFrame.
        Returns:
            pd.DataFrame: DataFrame containing the flattened XML records.
        Raises:
            ET.ParseError: If an XML parsing error occurs.
        """
        records = []
        try:
            # Stream parse to handle large XML files efficiently
            context = ET.iterparse(self.xml_file, events=("end",))
            for event, elem in context:
                # Adjust the tag check according to your XML schema
                if elem.tag.endswith("sdnEntry"):
                    record = self.flatten_element(elem)
                    records.append(record)
                    elem.clear()  # Free memory for processed elements
            print(f"Parsed {len(records)} records from XML.")
        except ET.ParseError as e:
            print(f"XML parsing error: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error during XML parsing: {e}")
            raise

        return pd.DataFrame(records)

    def save_to_db(self, data: pd.DataFrame, table_name="ofac_sdn", chunk_size: int = 1000):
        """
        Split the DataFrame into chunks and save them to the database using SQLAlchemy.
        The first chunk will be inserted with 'replace' (creating/replacing the table),
        and subsequent chunks will be appended.

        Args:
            data (pd.DataFrame): DataFrame to store.
            table_name (str): The name of the table in the database.
            chunk_size (int): The number of rows per chunk.

        Raises:
            Exception: If there is a problem storing data to the database.
        """
        if not self.connection:
            print("Database connection string not provided. Skipping database storage.")
            return

        try:
            total_rows = len(data)
            # If the DataFrame is empty, do nothing
            if total_rows == 0:
                print("No data to save.")
                return

            # Calculate the number of chunks
            num_chunks = (total_rows - 1) // chunk_size + 1

            for i in range(num_chunks):
                start_idx = i * chunk_size
                end_idx = start_idx + chunk_size
                chunk = data.iloc[start_idx:end_idx]
                # For the first chunk, use 'replace'; for subsequent chunks, use 'append'
                mode = "replace" if i == 0 else "append"
                print(f"Saving rows {start_idx} to {min(end_idx, total_rows)} with mode '{mode}'.")
                self.connection.insert(
                    df=chunk,
                    table=table_name,
                    schema=SCHEMA,  # Assumes SCHEMA is defined in the class or module scope
                    if_exists=mode,
                )
        except Exception as e:
            print(f"Unexpected error saving to database: {e}")
            raise

    def process(self):
        """
        Execute the full processing pipeline: download, parse, save CSV, and store in database.
        Returns:
            pd.DataFrame: The parsed DataFrame.
        """
        if not os.path.exists(self.xml_file):
            self.download_xml()
        df = self.parse_xml_to_dataframe()

        self.orm_insertion(df)
        # self.save_csv(df)
        # self.save_to_db(df)
        return df

    def orm_insertion(self, df):

        from controllers.handlers import NameHandler
        name_handler = NameHandler()

        for idx, row in enumerate(df.itertuples(index=False)):

            if row.sdnType.upper() == RecoType.ENTITY.name:
                name = row.lastName
                # language = name_handler.detect_language(name)
            elif row.sdnType.upper() == RecoType.INDIVIDUAL.name:
                name = f"{row.firstName} {row.lastName}"
                # language = name_handler.detect_language(name)
            else:
                # print(row.sdnType)
                print("Unknown 'sdnType' for the user")
                continue


            # if language not in [rt.value for rt in SupportedLanguage]:
            #     print(language)
            #     print("Unsupported language for the user")
            #     continue


            hash = name_handler.hash(
                name=name,
                type=row.sdnType,
                # language=language
            )

            print(row.uid, row.firstName, row.lastName, row.sdnType, hash)
            sanc = Sanctions(
                uid=row.uid,
                first_name=row.firstName,
                last_name=row.lastName,
                type=row.sdnType,
                # language=language,
                search_hash=str(hash),
            )


            self.factory.add(sanc)

            if idx % 999 == 0:
                self.factory.commit()
        self.factory.commit()
        pass


if __name__ == "__main__":
    # Example usage:
    # Set your desired URL and database connection string.
    OFAC_XML_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
    DB_CONNECTION_STRING = "sqlite:///ofac.db"  # Example: SQLite database

    # processor = OFACDataProcessor(
    #     url=OFAC_XML_URL,
    #     xml_file="sdn.xml",
    # )
    #
    # try:
    #     df = processor.process()
    # except Exception as error:
    #     print(f"Processing failed: {error}")
