from time import sleep
import pandas
from lxml import html
from urllib.parse import unquote
import re
from urllib.parse import quote
from email_notification import send_email_with_attachment
from datetime import datetime
from random import randint, choice
from tqdm import tqdm
from itertools import cycle
from curl_cffi import requests
import logging

logging.basicConfig(filename='app_fingerprint.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# https://docs.google.com/spreadsheets/d/19SDtIF0LLCUtZEqslFIjXmBgS28FKhVTB-TlCsD7peM/edit#gid=1329028334

PRICE_MULTIPLIER = 1.065  # Change to None if not

MIN_REVIEWS_COUNT = 0
INPUT_FILE = "input.csv"
OUTPUT_FILE = f"output_{str(datetime.now().date())}.csv"

SENDER_EMAIL = "example@mail.com"
SENDER_EMAIL_PASS = ""

emails_to_notify = ["felixhkerr@gmail.com", "jtabraddon@aol.co.uk"]

PROXY_LIST = [
        'http://login:password@ip:port',
        'http://login:password@ip:port',
        ]


def parse(page, current_year):
    doc = html.fromstring(page)
    data = {}

    for i in doc.xpath(
        '//div[@class="js-offers-container"]/div[@class="card offer-card "]/div[@class="offer-card__container"]'
    ):
        offer_case = next(
            iter(i.xpath('.//span[contains(@class, "badge-cases")]/text()')), None
        )

        if offer_case:
            if (
                "6 btls" in offer_case.lower()
                or "9 btls" in offer_case.lower()
                or "12 btls" in offer_case.lower()
            ):
                item_year = i.xpath(
                    './/div[@class="offer-card__badges"]/span[1]/text()'
                )[0]
                if int(item_year) == int(current_year):
                    store_page = i.xpath(
                        './div[@class="col1"]/a[@class="offer-card__merchant-name"]/@href'
                    )[0]
                    store_name = i.xpath(
                        './div[@class="col1"]/a[@class="offer-card__merchant-name"]/text()'
                    )[0]
                    rating = i.xpath('./div[@class="col1"]/span/@aria-label')[0]
                    location = i.xpath(
                        './div[@class="col1"]/div[@class="offer-card__location"]/div[contains(@class, "offer-card__location-address")]/text()'
                    )[0]
                    if "uk" in location.split(":")[0].strip().lower():
                        store_website = i.xpath("./a/@href")[0]

                        # price parse
                        sel_price = i.xpath(
                            './a//div[@class="price offer-card__prices"]//div[contains(@class, "price__detail_secondary")]'
                        )[0]
                        if (
                            "750ml"
                            in sel_price.xpath("./@title")[0]
                            .strip()
                            .replace(" ", "")
                            .lower()
                        ):
                            price = " ".join(
                                sel_price.xpath(".//text()")
                            )

                            year = i.xpath('./div[@class="col3"]/div/span[1]/text()')[0]
                            case = i.xpath('./div[@class="col3"]/div/span[2]/text()')[0]

                            data["store_name"] = store_name
                            data["store_page"] = (
                                "https://www.wine-searcher.com" + store_page
                            )
                            data["store_website"] = unquote(store_website)
                            data["rating"] = rating
                            data["location"] = re.sub(r"\s+", " ", location)
                            data["price"] = price
                            data["year"] = year
                            data["case"] = case

                            return price
                    else:
                        print("NON:", location.split(":")[0].strip().lower())


def fetch_page(url, i=0, impersonate='chrome110'):
    i += 1
    proxy = choice(PROXY_LIST)
    proxy = {"https": f"{proxy}"}
    pause = randint(2, 5) * 0.10
    try:
        response = requests.get(url, impersonate=impersonate, proxies=proxy, timeout=80)
    except Exception as e:
        logging.error(f'В fetch_page exception {e}')
        sleep(pause)
        browser = ['chrome99', 'chrome100', 'chrome101', 'chrome104', 'chrome107', 'chrome110']

        return fetch_page(url, impersonate=choice(browser))

    if response.ok:
        print("Success")
        return response.text
    else:
        if response.status_code == 400:
            logging.error(f'Статус код 400: \n{url}')

        elif response.status_code == 403:
            sleep(pause)
            browser = ['chrome99', 'chrome100', 'chrome101', 'chrome104', 'chrome107', 'chrome110']
            return fetch_page(url, impersonate=choice(browser))

        else:
            logging.error(f'{response.status_code} {url}\n')

        sleep(pause)
        return fetch_page(url, i)


def main():
    df = pandas.read_csv(INPUT_FILE)
    data = []
    for index, row in tqdm(df.iterrows()):
        searching_key = row.get("Name")
        vintage = row.get("Attribute 1 value(s)")
        print(f"row:{index}")
        print(vintage)
        print(searching_key)
        print(row.get("Regular price"))
        print("---")

        searching_key = quote(searching_key)
        url = f"https://www.wine-searcher.com/find/{searching_key}/{vintage}/uk/-/i?Xcurrencycode=GBP&Xtax_mode=e&Xsort_order=e&Xsavecurrency=Y&_pjax=%23pjax-offers"

        try:
            page = fetch_page(url)
            if not page:
                continue
            price = parse(page, vintage)
            if price:
                print(f"Price: {price}")
                # FIXED PRICE PARSING
                match = re.findall(r"[\d,.]+", price)
                if match:
                    price_amount = match[0].replace(",", "").replace(" ", "")
                    price_amount = float(price_amount)
                    if PRICE_MULTIPLIER:
                        price_amount *= PRICE_MULTIPLIER
                    price = str(price_amount)

            row["Regular price"] = price
            data.append(row.copy())

        except Exception as e:
            print(e)
            row["Regular price"] = None
            data.append(row.copy())

    df_new = pandas.DataFrame(data)
    df_new.to_csv(OUTPUT_FILE, index=False)

    for email in emails_to_notify:
        send_email_with_attachment(
            "smtp.gmail.com",
            587,
            SENDER_EMAIL,
            SENDER_EMAIL_PASS,
            f"Hello there, csv update {str(datetime.now().date())} here",
            f"{str(datetime.now().date())} csv update",
            email,
            OUTPUT_FILE,
        )


if __name__ == "__main__":
    main()
