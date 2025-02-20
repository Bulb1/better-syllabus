import time
import re
import yaml
from collections import Counter
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Konfiguracja Firefoksa i Geckodrivera
service = Service("/usr/local/bin/geckodriver")
options = webdriver.FirefoxOptions()
options.add_argument("--headless")
driver = webdriver.Firefox(service=service, options=options)

main_url = "https://krk.prz.edu.pl/plany.pl?lng=PL&W=E&K=F&KW=&TK=html&S=70&P=&C=2023&erasmus=&O="
driver.get(main_url)
time.sleep(2)

# Pobieranie nazw przedmiotów
subject_elements = driver.find_elements(By.XPATH, '//td[@class="left"]/a')
subject_names = [el.text.strip().lower() for el in subject_elements]

# Liczenie wystąpień przedmiotów
subject_counts = Counter(subject_names)

driver.quit()

# Wczytanie istniejącego rules.yaml
try:
    with open("rules.yaml", "r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
except FileNotFoundError:
    config = {}

special_ranges = config.get("special_ranges", {})
special_subjects = set(config.get("special_subjects", []))

# Aktualizacja special_ranges i special_subjects
for subject, count in subject_counts.items():
    if count > 1:
        special_ranges[subject] = count-1 # Jak jakiś przedmiot jest 4 razy to zakres jest np. 3-6 nie 3-7
        special_subjects.add(subject)

# Zapis do rules.yaml
new_config = {
    "special_ranges": special_ranges,
    "special_subjects": list(special_subjects)
}

with open("rules.yaml", "w", encoding="utf-8") as file:
    yaml.dump(new_config, file, allow_unicode=True, default_flow_style=False)

print("Plik rules.yaml został zaktualizowany.")