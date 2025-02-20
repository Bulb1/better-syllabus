import csv
import time
import re
import yaml
from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Wczytanie konfiguracji z rules.yaml
with open("rules.yaml", "r", encoding="utf-8") as file:
    config = yaml.safe_load(file)

special_ranges = config.get("special_ranges", {})
# Używamy lower() aby później łatwo porównać z nazwami przedmiotów
special_ranges = {key.lower(): value for key, value in special_ranges.items()}

special_subjects = set(subject.lower() for subject in config.get("special_subjects", []))


def extract_main_info_from_row(row):
    """
    Pobiera z wiersza tabeli dane:
      - Semestr,
      - Przedmiot (nazwa),
      - Układ Zajęć (na podstawie kolumn W, C, L, P),
      - Suma godzin,
      - Punkty ECTS,
      - Egzamin (True/False),
      - Oblig. (True/False)
    """
    cells = row.find_elements(By.TAG_NAME, "td")
    if len(cells) < 11:
        return {}
    semestr = cells[0].text.strip()
    przedmiot = cells[2].text.strip()
    # Układ zajęć – łączymy godziny z kolumn W, C, L i P
    w = cells[3].text.strip()
    c = cells[4].text.strip()
    l = cells[5].text.strip()
    p = cells[6].text.strip()
    uklad_zajec = f"W{w} C{c} L{l} P{p}"
    suma_godzin = cells[7].text.strip()
    ects = cells[8].text.strip()

    # Przetwarzamy kolumnę egzamin – "T" (True) lub "N" (False)
    egzamin_text = cells[9].text.strip().upper()
    egzamin = True if egzamin_text == "T" else False

    # Przetwarzamy kolumnę Obligatoryjne
    # Jeśli znaleziono obrazek, pobieramy wartość atrybutu alt; w przeciwnym razie pobieramy tekst z komórki.
    imgs = cells[10].find_elements(By.TAG_NAME, "img")
    if imgs:
        oblig_text = imgs[0].get_attribute("alt").strip()
    else:
        oblig_text = cells[10].text.strip()
    # Jeżeli tekst odpowiada "Moduł obligatoryjny" (bez względu na wielkość liter), przyjmujemy True
    oblig = True if oblig_text.lower() == "moduł obligatoryjny" else False

    return {
        "Semestr": semestr,
        "Przedmiot": przedmiot,
        "Układ Zajęć": uklad_zajec,
        "Suma godzin": suma_godzin,
        "Punkty ECTS": ects,
        "Egzamin": egzamin,
        "Obligatoryjne": oblig
    }


def process_subject(subject_name, subject_url):
    """
    Przetwarza stronę przedmiotu i zwraca słownik z dodatkowymi danymi:
      - Katedra
      - Koordynatorzy
      - Asystenci
      - Treści kształcenia
      - Nakład pracy
      - Wystawianie Ocen
    """
    driver.get(subject_url)
    wait = WebDriverWait(driver, 10)

    def get_text(xpath):
        try:
            return wait.until(EC.presence_of_element_located((By.XPATH, xpath))).text.strip()
        except Exception:
            return ""

    # Pomijamy pobieranie danych dotyczących semestru, układu zajęć, ECTS itd.
    # gdyż zostaną one pobrane z głównej strony.

    # Pobieramy pozostałe dane (Katedra, Koordynatorzy, Asystenci, Treści kształcenia, Nakład pracy, Wystawianie Ocen)
    katedra = get_text('//span[text()="Nazwa jednostki prowadzącej zajęcia:"]/parent::div/following-sibling::div//b')

    coordinator_elements = driver.find_elements(
        By.XPATH, '//span[starts-with(text(),"Imię i nazwisko koordynatora")]/parent::div/following-sibling::div//b'
    )
    koordynatorzy = ", ".join([el.text.strip() for el in coordinator_elements])

    assistant_elements = driver.find_elements(
        By.XPATH,
        '//span[starts-with(text(),"semestr")]/parent::div/following-sibling::div[not(contains(@style,"clear:both"))]//b'
    )
    assistants_list = []
    for el in assistant_elements:
        text = el.text.strip()
        if ',' in text:
            text = text.split(',')[0].strip()
        if text:
            assistants_list.append(text)
    asystenci = ", ".join(assistants_list) if assistants_list else "nie ma asystentów"

    tresci_list = []
    try:
        tresci_rows = driver.find_elements(By.XPATH,
                                           '//table[thead//th[contains(text(),"Treści kształcenia")]]//tbody/tr')
        for row in tresci_rows:
            cols = row.find_elements(By.TAG_NAME, 'td')
            if len(cols) >= 4:
                tresc = cols[2].text.strip()
                realizacja = cols[3].text.strip()
                tresci_list.append(f"{tresc} - {realizacja}")
    except Exception:
        pass
    tresci_ksztalcenia = "\n".join(tresci_list)

    try:
        workload_table = driver.find_element(By.XPATH, '//table[thead//th[contains(text(),"Praca przed zajęciami")]]')
        workload_rows = workload_table.find_elements(By.XPATH, './/tbody/tr')
        workload_list = []
        for row in workload_rows:
            cells = row.find_elements(By.TAG_NAME, 'td')
            if len(cells) >= 4:
                forma = cells[0].text.strip()
                work_parts = [cells[i].text.strip() for i in range(1, 4) if cells[i].text.strip()]
                work = " ".join(work_parts)
                workload_list.append(f"{forma} - {work}")
        naklad_pracy = "\n".join(workload_list)
    except Exception:
        naklad_pracy = ""

    try:
        grading_table = driver.find_element(By.XPATH,
                                            '//table[thead//th[contains(text(),"Sposób wystawiania oceny podsumowującej")]]')
        grading_rows = grading_table.find_elements(By.XPATH, './/tbody/tr')
        grading_list = []
        for row in grading_rows:
            cells = row.find_elements(By.TAG_NAME, 'td')
            if len(cells) >= 2:
                forma = cells[0].text.strip()
                sposob = cells[1].text.strip()
                grading_list.append(f"{forma} - {sposob}")
        wystawianie_ocen = "\n".join(grading_list)
    except Exception:
        wystawianie_ocen = ""

    return {
        "Katedra": katedra,
        "Koordynatorzy": koordynatorzy,
        "Asystenci": asystenci,
        "Treści kształcenia": tresci_ksztalcenia,
        "Nakład pracy": naklad_pracy,
        "Wystawianie Ocen": wystawianie_ocen
    }


# Konfiguracja Firefoksa i Geckodrivera
service = Service("/usr/local/bin/geckodriver")
options = webdriver.FirefoxOptions()
options.add_argument("--headless")
driver = webdriver.Firefox(service=service, options=options)

main_url = "https://krk.prz.edu.pl/plany.pl?lng=PL&W=E&K=F&KW=&TK=html&S=70&P=&C=2023&erasmus=&O="
driver.get(main_url)
time.sleep(2)

# Pobieramy wszystkie przedmioty na głównej stronie wraz z dodatkowymi danymi z wiersza
subject_elements = driver.find_elements(By.XPATH, '//td[@class="left"]/a')
subject_links = []

for el in subject_elements:
    try:
        row = el.find_element(By.XPATH, "./ancestor::tr")
        main_info = extract_main_info_from_row(row)
        # Upewniamy się, że dane główne zostały pobrane
        if not main_info:
            continue
        name = main_info["Przedmiot"]
        href = el.get_attribute("href")
        is_module = "javascript:plany_getLnk" in href
        subject_links.append((name, href, is_module, main_info))
    except Exception as e:
        logger.error(f"Błąd przy pobieraniu danych z wiersza: {e}")

logger.info(f"Znaleziono {len(subject_links)} pozycji (przedmioty lub moduły).")

data = []
processed_special_subjects = set()

for idx, (subject_name, href, is_module, main_info) in enumerate(subject_links, start=1):
    subject_name_lower = subject_name.lower()
    # Jeśli przedmiot należy do specjalnych i już był przetworzony, pomijamy go
    if subject_name_lower in special_subjects and subject_name_lower in processed_special_subjects:
        logger.info(f"Przedmiot {subject_name} już przetworzony – pomijam.")
        continue

    if subject_name_lower in special_subjects:
        processed_special_subjects.add(subject_name_lower)

    logger.info(f"[{idx}/{len(subject_links)}] Przetwarzam: {subject_name}")

    if is_module:
        m = re.search(r"plany_getLnk\('([^']+)'\)", href)
        if m:
            module_relative = m.group(1)
            module_url = "https://krk.prz.edu.pl/" + module_relative
            driver.get(module_url)
            time.sleep(2)
            module_subject_elements = driver.find_elements(By.XPATH, '//td[@class="left"]/a')
            logger.info(f"Moduł '{subject_name}' zawiera {len(module_subject_elements)} przedmiotów.")

            # Pobierz dane z modułu przed rozpoczęciem nawigacji po poszczególnych przedmiotach
            module_subject_data = []
            for mod_el in module_subject_elements:
                try:
                    row = mod_el.find_element(By.XPATH, "./ancestor::tr")
                    mod_main_info = extract_main_info_from_row(row)
                    mod_sub_name = mod_main_info.get("Przedmiot", "").strip()
                    mod_sub_url = mod_el.get_attribute("href")
                    module_subject_data.append((mod_sub_name, mod_sub_url, mod_main_info))
                except Exception as e:
                    logger.error(f"Błąd przy pobieraniu danych z modułu: {e}")

            # Następnie iteruj po zebranych danych
            for mod_sub_name, mod_sub_url, mod_main_info in module_subject_data:
                try:
                    full_subject_name = f"{subject_name} - {mod_sub_name}"
                    mod_main_info["Przedmiot"] = full_subject_name
                    subject_data = process_subject(full_subject_name, mod_sub_url)
                    subject_data.update(mod_main_info)
                    data.append(subject_data)
                except Exception as e:
                    logger.error(f"Błąd przy przetwarzaniu przedmiotu {mod_sub_name}: {e}")
                time.sleep(1)
    else:
        try:
            subject_data = process_subject(subject_name, href)
            subject_data.update(main_info)
            data.append(subject_data)
        except Exception as e:
            logger.error(f"Błąd przy przetwarzaniu przedmiotu {subject_name}: {e}")
        time.sleep(1)

# Uaktualniamy listę kolumn CSV, dodając nowe pola pobierane z głównej strony
fieldnames = [
    "Semestr",
    "Przedmiot",
    "Układ Zajęć",
    "Suma godzin",
    "Punkty ECTS",
    "Egzamin",
    "Obligatoryjne",
    "Katedra",
    "Koordynatorzy",
    "Asystenci",
    "Treści kształcenia",
    "Nakład pracy",
    "Wystawianie Ocen"
]

csv_file = "przedmioty.csv"
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)

logger.info(f"Dane zapisane do pliku {csv_file}")
driver.quit()
