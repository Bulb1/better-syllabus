from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
import csv
from loguru import logger
import os
import yaml  # nowa biblioteka do zapisu YAML

# Tworzenie folderu output, jeśli nie istnieje
output_folder = "output"
os.makedirs(output_folder, exist_ok=True)

# Konfiguracja Firefoksa i Geckodrivera
service = Service("/usr/local/bin/geckodriver")
options = webdriver.FirefoxOptions()
options.add_argument("--headless")
driver = webdriver.Firefox(service=service, options=options)


def get_specialties_from_section(driver, section):
    """
    Pobiera specjalności (nazwy i URL-e) z danej sekcji (np. 'stacjonarne' lub 'niestacjonarne').
    Funkcja wyszukuje nagłówek <h4> z zadaną nazwą sekcji, a następnie zbiera wszystkie linki
    znajdujące się w kolejnych elementach do momentu, gdy pojawi się kolejny nagłówek.
    """
    specialties = []
    try:
        header_xpath = f"//h4[strong[contains(text(),'{section}')]]"
        header_elem = driver.find_element(By.XPATH, header_xpath)
        logger.info(f"Znaleziono nagłówek sekcji: {section}")

        # Pobieramy wszystkie rodzeństwa następujące po nagłówku
        siblings = header_elem.find_elements(By.XPATH, "following-sibling::*")
        for sib in siblings:
            # Jeśli natrafimy na kolejny nagłówek <h4>, kończymy zbieranie
            if sib.tag_name.lower() == "h4":
                break
            # Pobieramy wszystkie linki w obrębie aktualnego bloku (np. <ul>)
            links = sib.find_elements(By.XPATH, ".//li[@class='list-page']/a[1]")
            for link in links:
                name = link.text.strip()
                url = link.get_attribute("href")
                specialties.append((name, url))
        return specialties
    except Exception as e:
        logger.error(f"Błąd przy pobieraniu sekcji {section}: {e}")
        return specialties

try:
    # Krok 1: Wejście na stronę główną
    main_url = "https://weii.prz.edu.pl/studenci/plany-studiow"
    driver.get(main_url)
    logger.info("Załadowano stronę główną: " + main_url)

    # Przełączenie na iframe
    driver.switch_to.frame(driver.find_element(By.ID, "plany_iframe"))

    # --- Zbieranie dostępnych lat ze strony głównej ---
    # Na głównej stronie listy zawierają lata zapisane w formacie "YYYY/YYYY"
    years_elements = driver.find_elements(By.XPATH, "//li[@class='list-page']/a")
    years = [elem.text.strip() for elem in years_elements if "/" in elem.text]
    logger.info("Dostępne lata: " + str(years))

    # Wybieramy konkretny rok (np. '2023/2024')
    year = '2023/2024'
    link_year = driver.find_element(By.XPATH, f"//li[@class='list-page']/a[text()='{year}']")
    url_year = link_year.get_attribute("href")
    logger.info("Przechodzę do roku: " + url_year)
    driver.get(url_year)

    # --- Po wybraniu roku zbieramy dostępne kierunki ---
    major_elements = driver.find_elements(By.XPATH, "//li[@class='list-page']/a")
    # Przyjmujemy, że kierunki nie zawierają znaku "/" (który występuje w roku)
    majors = [elem.text.strip() for elem in major_elements if "/" not in elem.text and elem.text.strip() != ""]
    logger.info("Dostępne kierunki: " + str(majors))

    # Zapisujemy dane do pliku YAML o strukturze:
    # year:
    # - 2025/2026
    # - 2024/2025
    # major:
    # - Automatyka i robotyka
    # - Elektromobilność
    rules = {"year": years, "major": majors}
    with open("rules.yaml", "w", encoding="utf-8") as f:
        yaml.dump(rules, f, allow_unicode=True)
    logger.info("Zapisano dane do rules.yaml.")

    # Nawigacja do konkretnego kierunku (np. 'Informatyka')
    major = 'Informatyka'
    link_major = driver.find_element(By.XPATH, f"//li[@class='list-page']/a[text()='{major}']")
    url_major = link_major.get_attribute("href")
    logger.info("Przechodzę do kierunku: " + url_major)
    driver.get(url_major)

    # Pobierz specjalności z sekcji "stacjonarne"
    stacjonarne_specialties = get_specialties_from_section(driver, "stacjonarne")
    for name, url in stacjonarne_specialties:
        logger.info(f"stacjonarne: {name} -> {url}")

    # Pobierz specjalności z sekcji "niestacjonarne"
    niestacjonarne_specialties = get_specialties_from_section(driver, "niestacjonarne")
    for name, url in niestacjonarne_specialties:
        logger.info(f"niestacjonarne: {name} -> {url}")

    # Zapisz specjalności stacjonarne do pliku CSV
    stacjonarne_csv = os.path.join(output_folder, f"{major}_{year.replace('/', '-')}_stacjonarne.csv")
    with open(stacjonarne_csv, "w", newline='', encoding='utf-8') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Nazwa", "URL"])
        for name, url in stacjonarne_specialties:
            csvwriter.writerow([name, url])
            logger.info(f"Zapisano stacjonarne: {name} -> {url}")

    # Zapisz specjalności niestacjonarne do pliku CSV
    niestacjonarne_csv = os.path.join(output_folder, f"{major}_{year.replace('/', '-')}_niestacjonarne.csv")
    with open(niestacjonarne_csv, "w", newline='', encoding='utf-8') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Nazwa", "URL"])
        for name, url in niestacjonarne_specialties:
            csvwriter.writerow([name, url])
            logger.info(f"Zapisano niestacjonarne: {name} -> {url}")

    logger.info("Dane zostały zapisane do plików CSV.")

except Exception as e:
    logger.error("Wystąpił błąd: " + str(e))

finally:
    driver.quit()
