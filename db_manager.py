# db_manager.py
import sqlite3
import logging
from datetime import date

DATABASE_NAME = 'news_articles.db'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def init_db():
    """Initializes the database and creates the articles table if it doesn't exist."""
    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    publication_date DATE NOT NULL,
                    summary TEXT,
                    source TEXT NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_ai_related BOOLEAN DEFAULT NULL, -- Store AI check result
                    ai_checked_at TIMESTAMP DEFAULT NULL -- When AI check was performed
                )
            ''')
            conn.commit()
            logging.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database error during initialization: {e}")
        raise

def store_articles(articles, update_existing=False):
    """
    Stores a list of article dictionaries in the database.
    Uses INSERT OR IGNORE to avoid duplicates based on the UNIQUE URL constraint.
    
    Args:
        articles: List of article dictionaries
        update_existing: If True, will update existing articles instead of ignoring them
    """
    if not articles:
        logging.info("No articles provided to store.")
        return 0

    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    
    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            
            for article in articles:
                try:
                    # Ensure publication_date is a date object
                    pub_date = article.get('publication_date')
                    if isinstance(pub_date, str):
                        # Attempt to parse if it's a string (should ideally be date obj already)
                        from dateutil.parser import parse
                        pub_date = parse(pub_date).date()
                    elif not isinstance(pub_date, date):
                        logging.warning(f"Invalid date format for article '{article.get('title')}': {pub_date}. Skipping.")
                        skipped_count += 1
                        continue
                    
                    # Check if the URL already exists
                    cursor.execute('SELECT id FROM articles WHERE url = ?', (article.get('url', 'N/A'),))
                    existing = cursor.fetchone()
                    
                    if existing and update_existing:
                        # Update the existing article
                        cursor.execute('''
                            UPDATE articles 
                            SET title = ?, publication_date = ?, summary = ?, source = ?
                            WHERE url = ?
                        ''', (
                            article.get('title', 'N/A'),
                            pub_date,
                            article.get('summary', None),
                            article.get('source', 'N/A'),
                            article.get('url', 'N/A')
                        ))
                        if cursor.rowcount > 0:
                            updated_count += 1
                            logging.debug(f"Updated existing article: {article.get('title')}")
                    elif not existing:
                        # Insert new article
                        cursor.execute('''
                            INSERT INTO articles (title, url, publication_date, summary, source)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            article.get('title', 'N/A'),
                            article.get('url', 'N/A'),
                            pub_date,
                            article.get('summary', None), # Use None if summary is missing
                            article.get('source', 'N/A')
                        ))
                        if cursor.rowcount > 0:
                            inserted_count += 1
                            logging.debug(f"Inserted new article: {article.get('title')}")
                    else:
                        # Article exists but we're not updating
                        logging.debug(f"Skipped existing article: {article.get('title')}")
                        skipped_count += 1
                        
                except sqlite3.IntegrityError as e:
                    logging.warning(f"Database integrity error for article '{article.get('title')}': {e}")
                    skipped_count += 1
                except Exception as e:
                    logging.error(f"Error processing article '{article.get('title', 'N/A')}': {e}")
                    skipped_count += 1

            conn.commit()
            logging.info(f"Articles processed: {len(articles)}")
            logging.info(f"- New articles added: {inserted_count}")
            logging.info(f"- Existing articles updated: {updated_count}")
            logging.info(f"- Articles skipped: {skipped_count}")
            return inserted_count + updated_count
    except sqlite3.Error as e:
        logging.error(f"Database error during storing articles: {e}")
        return 0 # Indicate failure or no insertion

def get_articles_for_ai_check():
    """Fetches articles that haven't been checked by AI yet."""
    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, summary
                FROM articles
                WHERE is_ai_related IS NULL
            ''')
            # Fetch as dictionaries
            desc = cursor.description
            column_names = [col[0] for col in desc]
            articles = [dict(zip(column_names, row)) for row in cursor.fetchall()]
            return articles
    except sqlite3.Error as e:
        logging.error(f"Database error fetching articles for AI check: {e}")
        return []

def update_ai_check_result(article_id, is_ai_related_flag):
    """Updates the AI check result for a specific article."""
    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE articles
                SET is_ai_related = ?, ai_checked_at = CURRENT_TIMESTAMP
                WHERE id = ? AND is_ai_related IS NULL
            ''', (is_ai_related_flag, article_id))
            conn.commit()
            logging.debug(f"Updated AI check result for article ID {article_id} to {is_ai_related_flag}")
            return cursor.rowcount > 0 # Return True if update happened
    except sqlite3.Error as e:
        logging.error(f"Database error updating AI check for article ID {article_id}: {e}")
        return False

def get_ai_articles(target_date=None):
    """
    Fetches articles marked as AI-related, optionally filtered by publication date.
    """
    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
            cursor = conn.cursor()
            if target_date:
                 query = '''
                    SELECT id, title, url, publication_date, summary, source
                    FROM articles
                    WHERE is_ai_related = 1 AND publication_date = ?
                    ORDER BY publication_date DESC, added_at DESC
                '''
                 cursor.execute(query, (target_date,))
            else:
                 query = '''
                    SELECT id, title, url, publication_date, summary, source
                    FROM articles
                    WHERE is_ai_related = 1
                    ORDER BY publication_date DESC, added_at DESC
                '''
                 cursor.execute(query)

            articles = [dict(row) for row in cursor.fetchall()]
            return articles
    except sqlite3.Error as e:
        logging.error(f"Database error fetching AI articles: {e}")
        return []

if __name__ == '__main__':
    # Example usage: Initialize DB when script is run directly
    logging.info("Initializing database...")
    init_db()
    logging.info("Database check/initialization complete.")
    # You could add test data insertion here if needed