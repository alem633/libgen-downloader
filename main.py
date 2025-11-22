import argparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import sys
import json

# -------- ARGS --------

parser = argparse.ArgumentParser(description="Libgen scraper")

parser.add_argument("--nocurl", action="store_true", help="Enable no curl mode (reads local files instead of curling)")
parser.add_argument("--debug", action="store_true", help="Enable debug mode, writes output to files")
#parser.add_argument("--query", "-q", required=True, help="Search query (e.g. book title)")
parser.add_argument("queries", nargs='+', help="One or more search queries (e.g. book titles)")
parser.add_argument("--depth", "-d", required=False, help="Max results")

args = parser.parse_args()

# -------- GLOBALS --------

BASE_URL = "https://libgen.li"
BASE_MIRROR_URL = "ads.php?md5="
BASE_DIRECT_DL_URL = "get.php?md5="

OUTPUT_DIR = "."

DEBUG_DIR = "debug"
DEBUG_HTML_FILENAME = "output.html"
DEBUG_MIRRORS_FILENAME = "libgen_mirrors_ids.txt"
DEBUG_DDL_IDS_FILENAME = "ddl_ids.txt"

depth = 100
if args.depth:
    depth = args.depth

with open('headers.json', 'r') as f:
    headers = json.load(f)

cookies = {'gmode': 'on'}

# -------- Functions --------

def get_libgen_mirror_ids(soup):
    libgen_mirror_ids = []

    table = soup.find('table', id='tablelibgen')
    if not table:
        return libgen_mirror_ids

    mirrors = table.find_all('a', attrs={'href': True})

    for mirror in mirrors:
        r_href = mirror.get('href')
        if BASE_MIRROR_URL in r_href:
            libgen_mirror_ids.append(r_href.split(BASE_MIRROR_URL)[-1].strip('"'))

    return libgen_mirror_ids

def fetch_ddl_id(mirror_link):
    try:
        r = session.get(mirror_link, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', id='main')
        if not table:
            return []
        ddl_ids = []
        for ddl_link in table.find_all('a', href=True):
            href = ddl_link['href']
            if BASE_DIRECT_DL_URL in href:
                ddl_ids.append(href.split(BASE_DIRECT_DL_URL)[-1].strip('"'))
        return ddl_ids
    except Exception as e:
        if args.debug:
            print(f"Errore su {mirror_link}: {e}")
        return []

def get_direct_dl_ids(mirror_page_links):
    ddl_ids = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(fetch_ddl_id, url): url for url in mirror_page_links}
        for future in as_completed(future_to_url):
            try:
                result = future.result()
                ddl_ids.extend(result)
            except Exception as e:
                if args.debug:
                    print(f"Errore nel risultato: {e}")
    return ddl_ids

session = requests.Session()
session.headers.update(headers)

def scrape(query):
    # -------- Request --------
    
    params = {
        'req': query,
        'res': depth,
        'gmod': 'on',
        'filesuns': 'all',
    }

    if not args.nocurl:
        r = requests.get(BASE_URL, params=params, cookies=cookies, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')

    if args.nocurl:
        with open(DEBUG_DIR + "/" + DEBUG_HTML_FILENAME, "r") as f:
            soup = BeautifulSoup(f.read(), 'html.parser')

    # ----- Local vars -----

    # follows the format BASE_URL + '/' + BASE_MIRROR_URL + libgen_mirror_ids[i]
    mirror_page_links = []
    libgen_mirror_ids = []

    # follows the format BASE_URL + '/' + BASE_DIRECT_DL_URL + ddl_ids[i]
    ddl_link = []
    ddl_ids = []

    # -------- Main Core --------
 
    if args.debug:
        with open(DEBUG_DIR + "/" + DEBUG_HTML_FILENAME, "w") as f:
            f.write(soup.prettify())

    if not args.nocurl:
        libgen_mirror_ids = get_libgen_mirror_ids(soup)

    if args.nocurl:
        with open(DEBUG_DIR + "/" + DEBUG_MIRRORS_FILENAME, "r") as f:
            libgen_mirror_ids = [line.strip() for line in f if line.strip()]

    if not libgen_mirror_ids:
        sys.exit("Couldn't find any mirrors")

    if args.debug:
        with open(DEBUG_DIR + "/" + DEBUG_MIRRORS_FILENAME, "w") as f:
            for id in libgen_mirror_ids:
                f.write(id + '\n')

    # -- Get direct dl links --
    for mirror_id in libgen_mirror_ids:
        mirror_page_links.append(BASE_URL + '/' + BASE_MIRROR_URL + mirror_id)

    if not args.nocurl:
        ddl_ids = get_direct_dl_ids(mirror_page_links)

    if args.nocurl:
        with open(DEBUG_DIR + "/" + DEBUG_DDL_IDS_FILENAME, "r") as f:
            ddl_ids = [line.strip() for line in f if line.strip()]

    if args.debug:
        with open(DEBUG_DIR + "/" + DEBUG_DDL_IDS_FILENAME, "w") as f:
            for id in ddl_ids:
                f.write(id + '\n')

    # -- Dump ddls to file -- 
    with open(OUTPUT_DIR + "/" + params['req'] + ".txt", "w") as f:
        for id in ddl_ids:
            f.write(BASE_URL + "/" + BASE_DIRECT_DL_URL + id + '\n')

def main():
    for query in args.queries:
        scrape(query)

if __name__ == "__main__":
    main()
