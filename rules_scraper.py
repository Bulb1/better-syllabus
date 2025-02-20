import time
from collections import Counter
import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service

# Konfiguracja Firefoksa i Geckodrivera
service = Service("/usr/local/bin/geckodriver")
options = webdriver.FirefoxOptions()
options.add_argument("--headless")
driver = webdriver.Firefox(service=service, options=options)

main_url = "https://krk.prz.edu.pl/plany.pl?lng=PL&W=E&K=F&KW=&TK=html&S=70&P=&C=2023&erasmus=&O="
driver.get(main_url)
time.sleep(2)

# Pobieramy wszystkie elementy zawierające nazwę przedmiotu
subject_elements = driver.find_elements(By.XPATH, '//td[@class="left"]/a')

subject_names = []
current_module = None  # Będziemy zapamiętywać nazwę aktualnego modułu

for el in subject_elements:
    text = el.text.strip().lower()
    href = el.get_attribute("href")
    # Jeżeli href zawiera "javascript:plany_getLnk", to traktujemy ten wiersz jako moduł
    if "javascript:plany_getLnk" in href:
        current_module = text
        subject_names.append(text)
    else:
        # Jeżeli mamy już ustalony aktualny moduł i tekst zaczyna się od "<moduł> -"
        # ale nie zawiera jeszcze podwójnego prefiksu, to dodajemy go.
        prefix = f"{current_module} -"
        double_prefix = f"{current_module} - {current_module}"
        if current_module is not None and text.startswith(prefix) and not text.startswith(double_prefix):
            new_text = f"{current_module} - {text}"
            subject_names.append(new_text)
        else:
            subject_names.append(text)

# Liczymy wystąpienia dla każdego przedmiotu
subject_counts = Counter(subject_names)
driver.quit()

# Wczytanie istniejącego pliku rules.yaml lub utworzenie pustej konfiguracji
try:
    with open("rules.yaml", "r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
except FileNotFoundError:
    config = {}

special_ranges = config.get("special_ranges", {})
special_subjects = set(config.get("special_subjects", []))

# Dla przedmiotów, które pojawiają się więcej niż raz, ustawiamy zakres (ilość powtórzeń pomniejszoną o 1)
for subject, count in subject_counts.items():
    if count > 1:
        special_ranges[subject] = count - 1  # np. gdy przedmiot występuje 4 razy, zakres to 3
        special_subjects.add(subject)

new_config = {
    "special_ranges": special_ranges,
    "special_subjects": list(special_subjects)
}

with open("rules.yaml", "w", encoding="utf-8") as file:
    yaml.dump(new_config, file, allow_unicode=True, default_flow_style=False)

print("Plik rules.yaml został zaktualizowany.")
