# ai_filter.py
import google.generativeai as genai
import os
import logging
import time
from db_manager import get_articles_for_ai_check, update_ai_check_result
from dotenv import load_dotenv # Import dotenv here too

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global scope configuration attempt ---
# Note: load_dotenv() should ideally be called *before* this in the main script (app.py)
# This global configuration relies on the environment being set *before* this module is imported heavily.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        logging.info("Gemini AI model configured successfully.")
    except Exception as e:
        logging.error(f"Error configuring Gemini AI globally: {e}")
        model = None
else:
     logging.warning("GEMINI_API_KEY not found in environment during initial module load.")


# Define the prompt for classification
AI_CHECK_PROMPT_TEMPLATE = """
Analyze the following article title and summary.
Is the article primarily about Artificial Intelligence (AI), machine learning, large language models, generative AI, neural networks, or closely related AI subfields?

Title: "{title}"
Summary: "{summary}"

Answer ONLY with "Yes" or "No".
"""

MAX_RETRIES = 3
RETRY_DELAY = 5 # seconds

def is_article_ai_related(title, summary):
    # ... (function remains the same, relies on the globally configured 'model') ...
    if not model:
        logging.error("Gemini AI model is not available (was not configured).")
        return None # Indicate AI check couldn't be performed

    if not title:
        logging.warning("Cannot check article without a title.")
        return None

    prompt = AI_CHECK_PROMPT_TEMPLATE.format(
        title=title,
        summary=summary if summary else "No summary available." # Handle missing summary
    )

    retries = 0
    while retries < MAX_RETRIES:
        try:
            # Use the safety_settings argument to reduce refusals for simple Yes/No
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            response = model.generate_content(prompt, safety_settings=safety_settings)

            # Check if the response was blocked despite settings
            if not response.parts:
                 logging.warning(f"Gemini response blocked for '{title}'. Prompt: {prompt}. Treating as indeterminate.")
                 # You might decide to treat blocked responses differently, e.g., always False or None
                 if retries == MAX_RETRIES - 1:
                     return False # Assume 'No' after final retry if blocked
                 # Fall through to retry logic

            else:
                # Clean up the response text
                cleaned_response = response.text.strip().lower().replace('.', '') # Remove periods too

                if cleaned_response == 'yes':
                    logging.debug(f"AI classified '{title}' as AI-related.")
                    return True
                elif cleaned_response == 'no':
                    logging.debug(f"AI classified '{title}' as NOT AI-related.")
                    return False
                else:
                    logging.warning(f"Unexpected AI response for '{title}': '{response.text}'. Treating as indeterminate.")
                    if retries == MAX_RETRIES - 1:
                        return False # Assume 'No' after final retry fails to get clear answer


        except Exception as e:
            logging.error(f"Error calling Gemini API for article '{title}' (Attempt {retries+1}/{MAX_RETRIES}): {e}")
            if "rate limit" in str(e).lower():
                logging.warning("Rate limit likely hit. Waiting before retry...")

            retries += 1
            if retries < MAX_RETRIES:
                 logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                 time.sleep(RETRY_DELAY)
            else:
                 logging.error(f"Max retries reached for article '{title}'. AI check failed.")
                 return None # Indicate failure after retries

    return None


def process_articles_for_ai_theme():
    """Fetches unchecked articles from DB and updates them with AI classification."""
    global model # Make sure we're using the potentially configured model
    if not model: # Double check if model was configured
         # Try to configure again, maybe .env loaded later?
         load_dotenv() # Load .env specifically for this function if run standalone
         api_key = os.environ.get("GEMINI_API_KEY")
         if api_key:
              try:
                   genai.configure(api_key=api_key)
                   model = genai.GenerativeModel('gemini-1.5-flash-latest')
                   logging.info("Gemini AI model configured successfully within process function.")
              except Exception as e:
                   logging.error(f"Error configuring Gemini AI within process function: {e}")
                   model = None # Ensure it's None if config fails
         else:
              logging.error("Cannot process articles: GEMINI_API_KEY not found.")
              raise EnvironmentError("GEMINI_API_KEY not found. Cannot run AI check.") # Raise error

    logging.info("Starting AI theme check process...")
    articles_to_check = get_articles_for_ai_check()
    logging.info(f"Found {len(articles_to_check)} articles needing AI check.")

    processed_count = 0
    ai_related_count = 0

    for article in articles_to_check:
        article_id = article['id']
        title = article['title']
        summary = article.get('summary', '') # Use empty string if summary is None

        logging.debug(f"Checking article ID {article_id}: '{title}'")
        is_ai = is_article_ai_related(title, summary)

        if is_ai is not None: # Only update if AI check succeeded (returned True or False)
            if update_ai_check_result(article_id, is_ai):
                 processed_count += 1
                 if is_ai:
                    ai_related_count += 1
                 # Add a small delay to respect potential free tier rate limits
                 time.sleep(1.1) # Slightly more than 1 sec for ~60 RPM limit
            else:
                 logging.warning(f"Failed to update AI check status in DB for article ID {article_id}")
        else:
            logging.warning(f"AI check failed for article ID {article_id}. It will be retried later.")

    logging.info(f"AI theme check process completed. Processed: {processed_count}, Identified as AI-related: {ai_related_count}")
    return processed_count, ai_related_count

if __name__ == '__main__':
    print("Attempting to run AI filter standalone...")
    load_dotenv() # Load .env file if running this script directly
    api_key_present_standalone = bool(os.environ.get("GEMINI_API_KEY"))

    if not api_key_present_standalone:
         print("\nERROR: GEMINI_API_KEY not found in .env file or environment.")
         print("Please create a .env file in the script's directory with:")
         print("GEMINI_API_KEY=YOUR_API_KEY_HERE")
    else:
        print("API Key found. Running AI theme check on articles from the database...")
        # Ensure DB exists first if running standalone
        from db_manager import init_db
        try:
            init_db()
            process_articles_for_ai_theme()
            print("AI check process finished.")
        except Exception as e:
            print(f"An error occurred: {e}")