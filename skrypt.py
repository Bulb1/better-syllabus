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

def process_subject(subject_name, subject_url):
    """
    Przetwarza stronę przedmiotu i zwraca słownik z danymi:
      - Semestr (dla wyjątkowych przedmiotów ustawiamy zakres, np. "1 - 2")
      - Przedmiot (w którym dołączamy informację o ECTS)
      - Układ Zajęć
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

    # Wydobywanie informacji o planie zajęć, ECTS oraz semestrze
    try:
        schedule_str = wait.until(EC.presence_of_element_located(
            (By.XPATH, '//span[text()="Układ zajęć w planie studiów:"]/parent::div/following-sibling::div//b')
        )).text.strip()
        # Przykładowy format: "sem: 1 / W30 C45   / 6 ECTS / E"
        parts = schedule_str.split("/")
        if len(parts) >= 1:
            sem_info = parts[0].strip()
            match = re.search(r"sem:\s*(\d+)", sem_info, re.IGNORECASE)
            semester = match.group(1) if match else ""
        else:
            semester = ""

        if len(parts) >= 3:
            uklad_zajec = parts[1].strip()
            ects = parts[2].strip()
        else:
            uklad_zajec = ""
            ects = ""
    except Exception:
        uklad_zajec = ""
        ects = ""
        semester = ""

    # Dołączamy informację o ECTS do nazwy przedmiotu (jeśli istnieje)
    if ects:
        subject_name = f"{subject_name} {ects}"

    # Ustawienie zakresu semestru dla przedmiotów ze specjalnymi regułami
    range_offset = None
    # Porównujemy z uwzględnieniem lower case
    for prefix, offset in special_ranges.items():
        if subject_name.lower().startswith(prefix):
            range_offset = offset
            break

    if range_offset is not None:
        try:
            sem_int = int(semester)
            semester = f"{sem_int} - {sem_int + range_offset}"
        except ValueError:
            pass

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
        "Semestr": semester,
        "Przedmiot": subject_name,
        "Układ Zajęć": uklad_zajec,
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

subject_elements = driver.find_elements(By.XPATH, '//td[@class="left"]/a')
subject_links = []
for el in subject_elements:
    name = el.text.strip()
    href = el.get_attribute("href")
    is_module = "javascript:plany_getLnk" in href
    subject_links.append((name, href, is_module))

logger.info(f"Znaleziono {len(subject_links)} pozycji (przedmioty lub moduły).")

data = []
processed_special_subjects = set()

for idx, (subject_name, href, is_module) in enumerate(subject_links, start=1):
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

            module_subjects = {}
            for mod_el in module_subject_elements:
                try:
                    mod_sub_name = mod_el.text.strip()
                    mod_sub_url = mod_el.get_attribute("href")
                    full_subject_name = f"{subject_name} - {mod_sub_name}"
                    module_subjects[full_subject_name] = mod_sub_url
                except Exception as e:
                    logger.error(f"Błąd przy odczycie elementu modułu: {e}")

            for full_subject_name, mod_sub_url in module_subjects.items():
                try:
                    subject_data = process_subject(full_subject_name, mod_sub_url)
                    data.append(subject_data)
                except Exception as e:
                    logger.error(f"Błąd przy przetwarzaniu przedmiotu {full_subject_name}: {e}")
                time.sleep(1)
            driver.get(main_url)
            time.sleep(2)
    else:
        try:
            subject_data = process_subject(subject_name, href)
            data.append(subject_data)
        except Exception as e:
            logger.error(f"Błąd przy przetwarzaniu przedmiotu {subject_name}: {e}")
        time.sleep(1)

csv_file = "przedmioty.csv"
fieldnames = ["Semestr",
              "Przedmiot",
              "Układ Zajęć",
              "Katedra",
              "Koordynatorzy",
              "Asystenci",
              "Treści kształcenia",
              "Nakład pracy",
              "Wystawianie Ocen"
              ]

with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)

logger.info(f"Dane zapisane do pliku {csv_file}")
driver.quit()
