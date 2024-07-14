import subprocess
import requests
import bz2
import os
import pathlib
import time
import logging
import pandas as pd
import requests
import nltk
nltk.download('stopwords')
nltk.download('punkt')
from rake_nltk import Rake
from selenium import webdriver
from PIL import Image
from googlesearch import search
from bs4 import BeautifulSoup


MASTER_DATA_FOLDER = "../database/"
SCRAPED_DATA_FOLDER = "scraped_data/"
EXTERNAL_DATASETS = "external_dataset/"
SCREENSHOT_FOLDER = MASTER_DATA_FOLDER + SCRAPED_DATA_FOLDER + "screenshots/"
WEBSITE_FOLDER = MASTER_DATA_FOLDER + SCRAPED_DATA_FOLDER + "website_dumps/"

extracted_db = pd.DataFrame(columns=["id", "url","target", "verified", "phish_pic_path", "target_pic_path", "phish_dump_path", "target_dump_path"])

def _perform_google_search(search_term: str) -> str:
    """
    This function performs a google search using the given search term.

    Args:
        search_term (str): This is a string containing the seach term.
    Returns:
        str: This string is the URL of top result from google.
    """
    print("Perform a Google Search.")
    for i in search(search_term, num=1, stop=1):
        top_search_result = i
        return top_search_result
    return ""

def _capture_website_screenshot(id: str, tag: str, url: str) -> str:
    """
    This function takes the screenshot of the provided url.

    Args:
        id (int): An integer that shows the id of the website, Used later for correlations.
        tag (str): A tag to be added when saving this website screenshot.
        url (str): A string representing the url to be downloaded.
    Returns:
        str : A string value containing the path where the screenshot is saved.
    """
    pathlib.Path(SCREENSHOT_FOLDER+str(id)).mkdir(parents=True, exist_ok=True)
    driver = webdriver.Firefox()
    driver.get(url)
    time.sleep(1)
    driver.save_screenshot(SCREENSHOT_FOLDER+str(id)+"/"+tag+".png")
    driver.quit()

    return SCREENSHOT_FOLDER+str(id)+"/"+tag+".png"

def _discover_keywords(url: str) -> list:
    """
    This function is used for discovering the keywords inside the phishing website.

    Args:
        url (str): A URL containing the phishing website link.
    Returns:
        list: A list of all keywords contained inside the phishing website.
    """
    rake_analyser = Rake()
    soup = BeautifulSoup(requests.get(url).text, 'html.parser')
    text =  soup.findAll(string=True)
    visible_words = " ".join(t.strip() for t in text)
    rake_analyser.extract_keywords_from_text(visible_words)
    keywords = rake_analyser.get_ranked_phrases()

    return keywords

def _download_website(id: str, tag: str, url: str) -> str:
    """
    This function takes the screenshot of the provided url.

    Args:
        id (int): An integer that shows the id of the website, Used later for correlations.
        tag (str): A tag to be added when saving this website.
        url (str): A string representing the url to be downloaded.
    Returns:
        str : A string value containing the path where the website dump is saved.
    """
    save_location = WEBSITE_FOLDER+str(id)+"/"+tag+"/"
    pathlib.Path(save_location).mkdir(parents=True, exist_ok=True)    
    subprocess.run(["wget","--max-redirect", "200",  "-p", "--convert-links",url, "-P", save_location])
    return save_location

def scrape_urls() -> None:
    """
    This function opens the current datasets and scrapes the url listed in them.

    Args:
        None
    Returns:
        None
    """
    logging.info("Scraping Data from Phishtank")
    phishtank_dataset = pd.read_csv(MASTER_DATA_FOLDER + EXTERNAL_DATASETS + "phish_tank_original.csv")

    # Some field values can be directly copied over.
    extracted_db["url"] = phishtank_dataset["url"]
    extracted_db["target"] = phishtank_dataset["target"]
    extracted_db["verified"] = phishtank_dataset["verified"]
    extracted_db["id"] = phishtank_dataset["phish_id"]
    extracted_db["dataset"] = "phishtank"

    for index, row in phishtank_dataset.iterrows():
        extracted_db.loc[extracted_db["id"] == row["phish_id"]]["phish_pic_path"] = _capture_website_screenshot(id=row["phish_id"],tag="phish", url=row["url"])
        extracted_db.loc[extracted_db["id"] == row["phish_id"]]["phish_dump_path"] = _download_website(id=row["phish_id"],tag="phish", url=row["url"])

        if row["target"] != "Other":
            top_url = _perform_google_search(row["target"])
        else:
            # Find out most common words used in the phishing website then search those terms.
            keywords = _discover_keywords(url=row["url"])
            top_url = _perform_google_search(search_term=" ".join(keywords[:1]))

        if top_url != "":
            extracted_db.loc[extracted_db["id"] == row["phish_id"]]["target_pic_path"] = _capture_website_screenshot(id=row["phish_id"],tag="target", url=top_url)
            extracted_db.loc[extracted_db["id"] == row["phish_id"]]["target_dump_path"] = _download_website(id=row["phish_id"],tag="target", url=top_url)
        else:
            extracted_db.loc[extracted_db["id"] == row["phish_id"]]["target_pic_path"] = None
            extracted_db.loc[extracted_db["id"] == row["phish_id"]]["target_dump_path"] = None

    return None

def refresh_datasets() -> None:
    """
    This function downloads the datasets and refreshes them if necessary.

    Args:
        None
    Returns:
        None
    """
    # Create the directory if it does not exists.
    pathlib.Path(MASTER_DATA_FOLDER + EXTERNAL_DATASETS).mkdir(parents=True, exist_ok=True)

    logging.info("Downloading PhishTank Database")
    dataset_path  = MASTER_DATA_FOLDER + EXTERNAL_DATASETS + "phish_tank_original.csv"
    refresh_required = True
    if os.path.exists(dataset_path):
        change_time = os.path.getmtime(dataset_path)
        if time.time() < change_time + 3600:
            refresh_required = False

    if refresh_required:
        phishtank_data = bz2.decompress(requests.get("http://data.phishtank.com/data/online-valid.csv.bz2").content)
        with open(dataset_path, "wb+") as file:
            file.write(phishtank_data)

    return None

def truncate_processed_database() -> None:
    """
    This function is used for truncating the processed datasets.

    Args:
        None
    Returns:
        None
    """
    logging.info("Truncating Processed Database")
    if os.path.exists("../database/processed_db.csv"):
        os.remove("../database/processed_db.csv")
    return None

def export_database() -> None:
    """
    This function is used for exporting the extracted database into a CSV file.

    Args:
        None
    Returns:
        None
    """
    logging.info("Exporting Extracted Database for Analysis.")
    extracted_db.to_csv("../database/extracted_db.csv")

def main() -> None:
    truncate_processed_database()
    refresh_datasets()
    scrape_urls()
    export_database()

if __name__ == "__main__":
    main()