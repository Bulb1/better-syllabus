import os
import csv
import re
import yaml
from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service

# Upewnij się, że folder output istnieje
output_folder = "output"
os.makedirs(output_folder, exist_ok=True)

# Wczytanie konfiguracji z config.yaml
with open("config.yaml", "r", encoding="utf-8") as file:
    config = yaml.safe_load(file)
special_ranges = {key.lower(): value for key, value in config.get("special_ranges", {}).items()}
special_subjects = {subject.lower() for subject in config.get("special_subjects", [])}

module_regex = re.compile(r"plany_getLnk\('([^']+)'\)")

def update_semester(subject_name, semester_value):
    for prefix, offset in special_ranges.items():
        if subject_name.lower().startswith(prefix):
            try:
                sem_int = int(semester_value)
                return f"{sem_int} - {sem_int + offset}"
            except ValueError:
                return semester_value
    return semester_value

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
    imgs = cells[10].find_elements(By.TAG_NAME, "img")
    if imgs:
        oblig_text = imgs[0].get_attribute("alt").strip()
    else:
        oblig_text = cells[10].text.strip()
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

    def get_text(xpath):
        try:
            element = driver.find_element(By.XPATH, xpath)
            return element.text.strip() if element else ""
        except Exception:
            return ""

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
options.set_preference("permissions.default.image", 2)
options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", False)
options.add_argument("--headless")

driver = webdriver.Firefox(service=service, options=options)
main_url = "https://krk.prz.edu.pl/plany.pl?lng=PL&W=E&K=F&KW=&TK=html&S=70&P=&C=2023&erasmus=&O="
driver.get(main_url)

# --- Ekstrakcja nazwy specjalności dla późniejszej nazwy pliku ---
try:
    specialty_element = driver.find_element(
        By.XPATH, '//div[@id="tresc-raportu"]/p[strong[contains(text(), "Specjalność")]]'
    )
    specialty_html = specialty_element.get_attribute("innerHTML")
    match = re.search(r"<strong>Specjalność:?</strong>\s*(.+)", specialty_html)
    if match:
        specialty = match.group(1).strip()
    else:
        raise ValueError("Nie znaleziono tekstu specjalności")
    specialty_filename = (
        specialty
        .replace("- ", "-")
        .replace(" -", "-")
        .replace(" ", "_")
        .replace("\n", "_")
    )
    specialty_filename = re.sub(r'[\/:*?"<>|]', '', specialty_filename)
    specialty_filename = specialty_filename + ".csv"
except Exception as e:
    logger.error("Nie można pobrać nazwy specjalności, używam domyślnej nazwy")
    specialty_filename = "specjalnosc.csv"

subject_elements = driver.find_elements(By.XPATH, '//td[@class="left"]/a')
subject_links = []
for el in subject_elements:
    try:
        row = el.find_element(By.XPATH, "./ancestor::tr")
        main_info = extract_main_info_from_row(row)
        if not main_info:
            continue
        name = main_info["Przedmiot"]
        href = el.get_attribute("href")
        is_module = "javascript:plany_getLnk" in href
        subject_links.append((name, href, is_module, main_info))
    except Exception as e:
        logger.error(f"Błąd przy pobieraniu danych z wiersza: {e}")

logger.info(f"Znaleziono {len(subject_links)} pozycji (przedmioty lub moduły).")

processed_subjects = set()
data = []
processed_modules = set()

for idx, (subject_name, href, is_module, main_info) in enumerate(subject_links, start=1):
    main_info["Semestr"] = update_semester(subject_name, main_info.get("Semestr", ""))
    logger.info(f"[{idx}/{len(subject_links)}] Przetwarzam: {subject_name}")

    if is_module:
        if subject_name in processed_modules:
            logger.info(f"Moduł {subject_name} już przetworzony – pomijam.")
            continue
        processed_modules.add(subject_name)

        m = module_regex.search(href)
        if m:
            module_relative = m.group(1)
            module_url = "https://krk.prz.edu.pl/" + module_relative
            driver.get(module_url)
            module_subject_elements = driver.find_elements(By.XPATH, '//td[@class="left"]/a')
            logger.info(f"Moduł '{subject_name}' zawiera {len(module_subject_elements)} przedmiotów.")

            module_subject_data = []
            for mod_el in module_subject_elements:
                try:
                    row = mod_el.find_element(By.XPATH, "./ancestor::tr")
                    mod_main_info = extract_main_info_from_row(row)
                    mod_sub_name = mod_main_info.get("Przedmiot", "").strip()
                    mod_sub_url = mod_el.get_attribute("href")
                    mod_main_info["Semestr"] = update_semester(mod_sub_name, mod_main_info.get("Semestr", ""))
                    module_subject_data.append((mod_sub_name, mod_sub_url, mod_main_info))
                except Exception as e:
                    logger.error(f"Błąd przy pobieraniu danych z modułu: {e}")

            for mod_sub_name, mod_sub_url, mod_main_info in module_subject_data:
                full_subject_name = f"{subject_name} - {mod_sub_name}"
                if full_subject_name in processed_subjects:
                    logger.info(f"Przedmiot {full_subject_name} już przetworzony – pomijam.")
                    continue
                processed_subjects.add(full_subject_name)

                try:
                    mod_main_info["Przedmiot"] = full_subject_name
                    subject_data = process_subject(full_subject_name, mod_sub_url)
                    subject_data.update(mod_main_info)
                    data.append(subject_data)
                except Exception as e:
                    logger.error(f"Błąd przy przetwarzaniu przedmiotu {mod_sub_name}: {e}")
    else:
        if subject_name in processed_subjects:
            logger.info(f"Przedmiot {subject_name} już przetworzony – pomijam.")
            continue
        processed_subjects.add(subject_name)
        try:
            subject_data = process_subject(subject_name, href)
            subject_data.update(main_info)
            data.append(subject_data)
        except Exception as e:
            logger.error(f"Błąd przy przetwarzaniu przedmiotu {subject_name}: {e}")

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

# Podział danych na dwa zbiory:
data_1_2 = []
data_others = []
for d in data:
    try:
        sem = d.get("Semestr", "")
        sem_num = int(sem.split()[0])
    except Exception:
        sem_num = None
    if sem_num is not None and sem_num <= 4:
        data_1_2.append(d)
    else:
        data_others.append(d)

# Zapis do CSV dla przedmiotów 1-4 semestr
if data_1_2:
    csv_file_1_2 = os.path.join(output_folder, "1-2rok.csv")
    with open(csv_file_1_2, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data_1_2)
    logger.info(f"Dane (semestry 1-4) zapisane do pliku {csv_file_1_2}")

# Zapis do CSV dla pozostałych przedmiotów – nazwa pliku pobrana z elementu HTML
if data_others:
    csv_file_specialty = os.path.join(output_folder, specialty_filename)
    with open(csv_file_specialty, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data_others)
    logger.info(f"Dane (semestry powyżej 4) zapisane do pliku {csv_file_specialty}")

driver.quit()
