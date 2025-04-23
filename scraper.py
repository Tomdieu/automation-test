# scraper.py
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta, date
from dateutil.parser import parse, ParserError
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Default URL if none is provided
DEFAULT_BBC_URL = "https://www.bbc.com/innovation"
BASE_BBC_URL = "https://www.bbc.com"
SOURCE_NAME = "BBC News"

# --- Update function definition to accept custom URL ---
def fetch_articles(news_url=DEFAULT_BBC_URL, source_name=None):
    """Fetches and parses articles from the provided BBC URL."""
    articles = []
    # Use provided source name or extract from URL if none provided
    if source_name is None:
        # Extract source name from URL (e.g., "innovation" from "/innovation")
        path_parts = news_url.split('/')
        if len(path_parts) > 3:
            section = path_parts[-1] or path_parts[-2]  # Use last non-empty part
            source_name = f"BBC {section.capitalize()}"
        else:
            source_name = "BBC News"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        logging.info(f"Fetching articles from URL: {news_url}")
        response = requests.get(news_url, headers=headers, timeout=20)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        time.sleep(1)

        soup = BeautifulSoup(response.content, 'html.parser')

        # --- Identify article containers ---
        # Let's find common card wrappers first. Look for divs with data-indexcard="true"
        potential_cards = soup.find_all('div', attrs={'data-indexcard': 'true'})
        logging.info(f"Found {len(potential_cards)} potential article cards.")

        processed_urls = set() # Keep track of URLs to avoid duplicates from different cards pointing to same article

        for card in potential_cards:
            article_data = {}

            # Find the link (usually the main wrapper is an 'a' tag or contains one)
            link_tag = card.find('a', href=True)
            if not link_tag or not link_tag['href']:
                 logging.debug("Skipping card, no valid link found.")
                 continue

            url = link_tag['href']
            # Handle relative URLs
            if url.startswith('/'):
                full_url = BASE_BBC_URL + url
            elif url.startswith('http'):
                 # Check if it's a BBC link or external (like newsletter signup)
                 if 'bbc.com' in url or 'bbc.co.uk' in url:
                     full_url = url
                 else:
                     logging.debug(f"Skipping non-BBC link: {url}")
                     continue # Skip external links like signups
            else:
                 logging.debug(f"Skipping invalid or non-article link: {url}")
                 continue # Skip javascript:void(0) or similar

            # Check if we've already processed this URL
            if full_url in processed_urls:
                logging.debug(f"Skipping duplicate URL: {full_url}")
                continue
            processed_urls.add(full_url)
            article_data['url'] = full_url


            # Find the headline (usually h2 or h3 within the link)
            headline_tag = link_tag.find(['h1', 'h2', 'h3'], attrs={'data-testid': lambda x: x and 'headline' in x})
            if not headline_tag:
                 headline_tag = link_tag.find(['h1', 'h2', 'h3']) # Fallback

            article_data['title'] = headline_tag.get_text(strip=True) if headline_tag else 'N/A'

            # Find the description/summary (usually a 'p' tag near the headline)
            # Search within the card, not just the link_tag
            description_tag = card.find('p', attrs={'data-testid': lambda x: x and 'description' in x})
            if not description_tag: # Fallback search if specific testid not found
                description_tag = card.find('p') # Might be less specific

            article_data['summary'] = description_tag.get_text(strip=True) if description_tag else None

             # Find the publication date/time
            # This is often in a span with testid 'card-metadata-lastupdated' within the card
            date_tag = card.find('span', attrs={'data-testid': 'card-metadata-lastupdated'})
            pub_date_str = date_tag.get_text(strip=True) if date_tag else None

            if pub_date_str:
                article_data['publication_date'] = parse_relative_date(pub_date_str)
            else:
                # Fallback: Look for time tags or other patterns if needed
                logging.debug(f"No publication date found for {article_data.get('title')}")
                article_data['publication_date'] = None # Mark as unknown

            article_data['source'] = source_name

            # Basic validation
            if article_data.get('title') not in ['N/A', ''] and article_data.get('publication_date'):
                articles.append(article_data)
            else:
                logging.debug(f"Skipping incomplete article data: Title='{article_data.get('title')}', Date='{article_data.get('publication_date')}'")


    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching URL {news_url}: {e}")
        return None # Return None on fetch failure
    except Exception as e:
        logging.error(f"An error occurred during scraping: {e}", exc_info=True) # Log full traceback
        return None # Return None on other scraping errors

    logging.info(f"Successfully parsed {len(articles)} unique articles with titles and dates.")
    return articles
# --- End of fetch_articles definition ---


# --- Ensure this function definition is correct ---
def filter_articles_by_date(articles, target_date):
    """Filters a list of articles to include only those published on the target_date."""
    if articles is None: # Handle case where fetch_articles failed
        logging.warning("Cannot filter articles because the input list is None.")
        return []
    if not isinstance(target_date, date):
        logging.error("Target date must be a date object.")
        return []

    filtered = [
        article for article in articles
        if article.get('publication_date') == target_date
    ]
    logging.info(f"Filtered {len(articles)} articles down to {len(filtered)} for date {target_date}.")
    return filtered
# --- End of filter_articles_by_date definition ---


# --- Ensure this function definition is correct ---
def parse_relative_date(date_str):
    """Parses relative date strings like 'X hrs ago', 'X days ago', 'yesterday'."""
    now = datetime.now()
    date_str_lower = date_str.lower()

    try:
        if 'yesterday' in date_str_lower:
            return (now - timedelta(days=1)).date()
        elif 'hr ago' in date_str_lower or 'hrs ago' in date_str_lower:
            hours = int(date_str_lower.split()[0])
            # Treat articles published less than 24 hours ago but on the same calendar day as today
            pub_time = now - timedelta(hours=hours)
            return pub_time.date()
            # return (now - timedelta(hours=hours)).date() # Original: might put recent articles on yesterday
        elif 'day ago' in date_str_lower or 'days ago' in date_str_lower:
            days = int(date_str_lower.split()[0])
            # Ensure minimum 1 day ago if specified
            if days == 0: days = 1
            return (now - timedelta(days=days)).date()
        elif 'min ago' in date_str_lower or 'mins ago' in date_str_lower:
             # Treat minutes ago as today
             return now.date()
        else:
            # Try parsing absolute dates like '15 Apr 2025' or '27 Mar 2025' etc.
            # Allow fuzzy parsing for different month formats etc.
             return parse(date_str, fuzzy=True).date()
    except (ValueError, IndexError, ParserError, OverflowError) as e: # Added OverflowError
        logging.warning(f"Could not parse date string '{date_str}': {e}")
        return None
# --- End of parse_relative_date definition ---


if __name__ == '__main__':
    logging.info("Fetching articles from BBC Innovation...")
    raw_articles = fetch_articles()

    if raw_articles:
        logging.info(f"\n--- Found {len(raw_articles)} articles ---")
        for i, art in enumerate(raw_articles[:5]): # Print first 5
            print(f"{i+1}. Title: {art.get('title')}")
            print(f"   URL: {art.get('url')}")
            print(f"   Date: {art.get('publication_date')}")
            print(f"   Summary: {art.get('summary')[:100] if art.get('summary') else 'N/A'}...")
            print("-" * 10)

        # Example: Filter for yesterday
        yesterday = date.today() - timedelta(days=1)
        logging.info(f"\n--- Filtering for articles published yesterday ({yesterday}) ---")
        yesterdays_articles = filter_articles_by_date(raw_articles, yesterday)
        if yesterdays_articles:
            logging.info(f"Found {len(yesterdays_articles)} articles from yesterday:")
            for art in yesterdays_articles:
                 print(f"- {art.get('title')} ({art.get('url')})")
        else:
             logging.info("No articles found from yesterday.")

    elif raw_articles is None:
        logging.error("Fetching articles failed.")
    else: # Empty list returned, fetch succeeded but found 0 articles
        logging.warning("No articles found on the page.")