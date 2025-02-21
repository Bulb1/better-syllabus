from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
import csv
from loguru import logger
import os

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

    # Nawigacja do rocznika "2023/2024"
    rok = '2023/2024'
    link_rok = driver.find_element(By.XPATH, f"//li[@class='list-page']/a[text()='{rok}']")
    url_rok = link_rok.get_attribute("href")
    logger.info("Przechodzę bezpośrednio do: " + url_rok)
    driver.get(url_rok)

    # Nawigacja do kierunku "Informatyka"
    kierunek = 'Informatyka'
    link_kierunek = driver.find_element(By.XPATH, f"//li[@class='list-page']/a[text()='{kierunek}']")
    url_kierunek = link_kierunek.get_attribute("href")
    logger.info("Przechodzę bezpośrednio do: " + url_kierunek)
    driver.get(url_kierunek)

    # Pobierz specjalności z sekcji "stacjonarne"
    stacjonarne_specialties = get_specialties_from_section(driver, "stacjonarne")
    for name, url in stacjonarne_specialties:
        logger.info(f"stacjonarne: {name} -> {url}")

    # Pobierz specjalności z sekcji "niestacjonarne"
    niestacjonarne_specialties = get_specialties_from_section(driver, "niestacjonarne")
    for name, url in niestacjonarne_specialties:
        logger.info(f"niestacjonarne: {name} -> {url}")

    # Zapisz specjalności stacjonarne do pliku CSV
    stacjonarne_csv = os.path.join(output_folder, f"{kierunek}_{rok.replace('/', '-')}_stacjonarne.csv")
    with open(stacjonarne_csv, "w", newline='', encoding='utf-8') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Nazwa", "URL"])
        for name, url in stacjonarne_specialties:
            csvwriter.writerow([name, url])
            logger.info(f"Zapisano stacjonarne: {name} -> {url}")

    # Zapisz specjalności niestacjonarne do pliku CSV
    niestacjonarne_csv = os.path.join(output_folder, f"{kierunek}_{rok.replace('/', '-')}_niestacjonarne.csv")
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