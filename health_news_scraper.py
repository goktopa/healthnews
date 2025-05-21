import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime
import platform
import re
import unicodedata
import time
import logging
import argparse
from urllib.parse import urljoin

print("Script started")
print(f"Current PATH: {os.environ['PATH']}")

# Desktop folder path for user 'pharm'
if platform.system() == "Windows":
    DESKTOP_PATH = os.path.join("C:\\Users\\pharm\\Desktop", "HealthNewsLinks")
else:
    DESKTOP_PATH = os.path.join(os.path.expanduser("~/Desktop"), "HealthNewsLinks")

# Create output directory if it doesn't exist
print(f"Attempting to create directory: {DESKTOP_PATH}")
try:
    if not os.path.exists(DESKTOP_PATH):
        os.makedirs(DESKTOP_PATH)
        print(f"Created directory: {DESKTOP_PATH}")
    test_file = os.path.join(DESKTOP_PATH, "test.txt")
    print(f"Testing write access with: {test_file}")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("test")
    os.remove(test_file)
    print(f"Confirmed write access to {DESKTOP_PATH}")
except Exception as e:
    print(f"Error: Cannot write to {DESKTOP_PATH}: {e}")
    exit(1)

# Set up logging after directory creation
print("Setting up logging")
logging.basicConfig(
    filename=os.path.join(DESKTOP_PATH, "scraper.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Configuration: List of reliable English-only health news sources
SOURCES = [
    {"name": "Healthline", "url": "https://www.healthline.com/health-news"},
    {"name": "WebMD", "url": "https://www.webmd.com/news"},
    {"name": "BBC Health", "url": "https://www.bbc.com/news/health"},
    {"name": "The Guardian Health", "url": "https://www.theguardian.com/society/health"},
    {"name": "Irish Times Health", "url": "https://www.irishtimes.com/health/"},
    {"name": "Sky News Health", "url": "https://news.sky.com/topic/health-10041"},
    {"name": "The Local Sweden Health", "url": "https://www.thelocal.se/tag/health"},
    {"name": "ANSA English Health", "url": "https://www.ansa.it/english/news/science_and_health/"},
    {"name": "Medical News Today", "url": "https://www.medicalnewstoday.com/news"},
    {"name": "Mayo Clinic News", "url": "https://newsnetwork.mayoclinic.org/discussion/"}
]

def clean_filename(text):
    """Clean text for use in filenames."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text).strip()
    text = re.sub(r'\s+', '_', text)
    return text[:50]  # Limit length for filesystem compatibility

def clean_text(text, for_body=True):
    """Clean text for body or titles, handling Unicode and special characters."""
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s.,!?\'"-]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if for_body else text.strip()

def scrape_article(url, source_name):
    """Scrape article title, headings, paragraphs, and quotes."""
    logging.info(f"Scraping article: {url}")
    print(f"Scraping article: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=60)  # Increased timeout
        response.raise_for_status()
        soup = BeautifulSoup(response.content.decode('utf-8', errors='replace'), "html.parser")

        # Check for English content
        lang = soup.find('html').get('lang', '').lower()
        if lang and not lang.startswith('en'):
            logging.warning(f"Skipping non-English page: {url}")
            print(f"Skipping non-English page: {url}")
            return "No Title", []

        # Extract title
        title_elem = soup.find("h1") or soup.find("title") or soup.find("h2")
        title = clean_text(title_elem.text, for_body=False) if title_elem else "No Title"

        # Extract structured content
        content = (soup.find("article") or
                   soup.find("div", class_=lambda x: x and any(k in x.lower() for k in ["article", "content", "news", "body"])) or
                   soup.find("main"))
        if not content:
            content = soup

        elements = []
        for elem in content.find_all(["h2", "h3", "p", "blockquote"]):
            if elem.name in ["h2", "h3"]:
                text = clean_text(elem.text, for_body=False)
                if text and len(text) > 10:
                    elements.append({"type": "heading", "level": elem.name, "text": text})
            elif elem.name == "p":
                text = clean_text(elem.text, for_body=True)
                if text and len(text) > 20:
                    elements.append({"type": "paragraph", "text": text})
            elif elem.name == "blockquote":
                text = clean_text(elem.text, for_body=True)
                if text and len(text) > 20:
                    elements.append({"type": "quote", "text": text})

        if not elements or len(elements) < 2:
            logging.warning(f"Insufficient content for {url}: {len(elements)} elements found")
            print(f"Insufficient content for {url}: {len(elements)} elements found")
            return title, []

        logging.info(f"Scraped: Title='{title}', Elements={len(elements)}")
        print(f"Scraped: Title='{title}', Elements={len(elements)}")
        return title, elements
    except Exception as e:
        logging.error(f"Error scraping {url}: {e}")
        print(f"Error scraping {url}: {e}")
        return "No Title", []

def save_article(title, elements, source, url, timestamp, idx):
    """Save article as a plain text file."""
    try:
        clean_title = clean_filename(title)
        txt_filename = os.path.join(DESKTOP_PATH, f"{source}_{clean_title}_{timestamp}_{idx}.txt")

        print(f"Generating text file: {txt_filename}")
        # Generate text content
        text_content = f"Source: {source}\n"
        text_content += f"URL: {url}\n"
        text_content += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        text_content += f"Title: {title}\n\n"

        for elem in elements:
            if elem["type"] == "heading":
                text_content += f"{'#' if elem['level'] == 'h2' else '##'} {elem['text']}\n\n"
            elif elem["type"] == "paragraph":
                text_content += f"{elem['text']}\n\n"
            elif elem["type"] == "quote":
                text_content += f"> {elem['text']}\n\n"

        # Save to text file
        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write(text_content)

        logging.info(f"Saved article to {txt_filename}")
        print(f"Saved article to {txt_filename}")
    except Exception as e:
        logging.error(f"Error saving article {txt_filename}: {e}")
        print(f"Error saving article {txt_filename}: {e}")

def fetch_health_news(max_articles_per_source=1):
    """Fetch articles from all sources."""
    all_articles = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    idx = 0

    for source in SOURCES:
        logging.info(f"Fetching from {source['name']} ({source['url']})")
        print(f"Fetching from {source['name']} ({source['url']})...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(source['url'], headers=headers, timeout=60)  # Increased timeout
            response.raise_for_status()
            soup = BeautifulSoup(response.content.decode('utf-8', errors='replace'), "html.parser")

            # Find article links
            article_links = []
            rejected_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # Convert relative URLs to absolute
                href = urljoin(source['url'], href)
                # Filter for health-related articles, avoiding category/index pages
                if (href.startswith("http") and
                    source['url'].rstrip("/").split("//")[1].split("/")[0] in href and
                    not any(exclude in href.lower() for exclude in [
                        "login", "signup", "advert", "privacy", "archive",
                        "category", "tag", "account", "settings", "subscribe", "newsletter",
                        "visa", "insurance", "podcast", "parsi", "video", "gallery", "comment",
                        "default.htm", "page=", "index"
                    ])):
                    # Source-specific filters
                    if source['name'] == "BBC Health":
                        if "health-" in href.lower() and href.count("/") >= 4:
                            article_links.append(href)
                        else:
                            rejected_links.append(href)
                    elif source['name'] == "WebMD":
                        if "/news/" in href.lower() and href.count("/") >= 5:
                            article_links.append(href)
                        else:
                            rejected_links.append(href)
                    elif source['name'] == "The Guardian Health":
                        if "/article/" in href.lower() or "/202" in href.lower():
                            article_links.append(href)
                        else:
                            rejected_links.append(href)
                    else:
                        if any(indicator in href.lower() for indicator in [
                            "article", "news/", "story", "202"
                        ]):
                            article_links.append(href)
                        else:
                            rejected_links.append(href)

            article_links = list(set(article_links))[:max_articles_per_source]
            if not article_links:
                logging.warning(f"No valid article links found for {source['name']}. Rejected: {rejected_links[:5]}")
                print(f"No valid article links found for {source['name']}. Rejected: {rejected_links[:5]}")
                continue

            # Scrape each article
            for link in article_links:
                print(f"Processing article: {link}")
                title, elements = scrape_article(link, source['name'])
                if elements:  # Only process if content exists
                    article = {
                        "source": source["name"],
                        "url": link,
                        "title": title,
                        "elements": elements
                    }
                    all_articles.append(article)
                    save_article(title, elements, source['name'], link, timestamp, idx)
                    idx += 1
                    time.sleep(1)  # Rate limiting
                else:
                    logging.warning(f"No content found for {link}")
                    print(f"No content found for {link}")
                time.sleep(1)  # Rate limiting between articles
        except Exception as e:
            logging.error(f"Error fetching from {source['name']}: {e}")
            print(f"Error fetching from {source['name']}: {e}")
            continue
        time.sleep(2)  # Rate limiting between sources
    return all_articles

def main():
    """Main function to fetch and save articles."""
    parser = argparse.ArgumentParser(description="Scrape health news and save as text files.")
    parser.add_argument("--max-articles", type=int, default=1, help="Max articles per source")
    args = parser.parse_args()

    print("Running health news fetch job...")
    logging.info("Starting health news fetch job")
    articles = fetch_health_news(max_articles_per_source=args.max_articles)
    if not articles:
        print("No articles found.")
        logging.info("No articles found.")
    else:
        print(f"Fetched and saved {len(articles)} articles.")
        logging.info(f"Fetched and saved {len(articles)} articles.")

if __name__ == "__main__":
    main()