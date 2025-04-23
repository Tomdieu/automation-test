# app.py
import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta, date
import time
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import functions from other modules AFTER loading .env
from db_manager import init_db, store_articles, get_ai_articles
from scraper import fetch_articles, filter_articles_by_date
from ai_filter import process_articles_for_ai_theme

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
PDF_FILENAME = "ai_news_report.pdf"
APP_TITLE = "AI News Article Extractor (BBC News)"

# Available BBC news sections for the dropdown
BBC_SECTIONS = {
    "BBC Innovation": "https://www.bbc.com/innovation",
    "BBC News Home": "https://www.bbc.com/news",
    "BBC Technology": "https://www.bbc.com/news/technology",
    "BBC Science": "https://www.bbc.com/news/science_and_environment",
    "BBC Business": "https://www.bbc.com/news/business",
}

# --- PDF Generation ---
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.font_loaded = False # Flag to track if DejaVu font loaded
        try:
            # Try to add the Unicode font.
            # Assumes .ttf files are in the same directory as app.py or accessible in system paths.
            # If these files are not present, the except block will handle it.
            self.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
            self.add_font("DejaVu", "B", "DejaVuSans-Bold.ttf", uni=True)
            self.add_font("DejaVu", "I", "DejaVuSans-Italic.ttf", uni=True)
            self.set_fallback_fonts(['DejaVu']) # Use DejaVu if character not in current font
            self.font_loaded = True # Set flag only if loading succeeds
            logging.info("DejaVu font loaded successfully. Using for PDF.")
        except (FileNotFoundError, RuntimeError) as e:
            # This block executes if the font files aren't found or FPDF has trouble
            logging.warning(f"DejaVu font not found or failed to load ({e}). Falling back to default fonts (may not support all characters).")
            # self.font_loaded remains False

    def _set_font_style(self, style='', size=10):
        """Helper to set font based on whether DejaVu loaded"""
        family = 'DejaVu' if self.font_loaded else 'Arial' # Use 'Arial' as fallback
        try:
            self.set_font(family, style, size)
        except RuntimeError:
            # If even Arial fails for some reason, log and maybe default to courier
            logging.error(f"Could not set font {family} {style} {size}. Trying Arial.")
            self.set_font('Arial', style, size) # Default safe fallback

    def _prepare_text(self, text_input):
        """Helper to encode text ONLY if using default (non-Unicode) fonts"""
        if self.font_loaded:
            # If DejaVu (Unicode) font is loaded, return text as is
            return str(text_input) # Ensure it's a string
        else:
            # If using default fonts (Arial), apply encoding safety for non-Latin-1 chars
            try:
                return str(text_input).encode('latin-1', 'replace').decode('latin-1')
            except Exception as e:
                logging.error(f"Error encoding text '{str(text_input)[:20]}...' for PDF: {e}")
                return "[Encoding Error]" # Placeholder for errors

    def header(self):
        self._set_font_style('B', 12)
        prepared_title = self._prepare_text(APP_TITLE)
        self.cell(0, 10, prepared_title, 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self._set_font_style('I', 8)
        prepared_footer = self._prepare_text(f'Page {self.page_no()}')
        self.cell(0, 10, prepared_footer, 0, 0, 'C')

    def chapter_title(self, title):
        self._set_font_style('B', 12)
        prepared_text = self._prepare_text(title)
        self.multi_cell(0, 6, prepared_text) # Use multi_cell for wrapping
        self.ln(5)

    def chapter_body(self, body):
        self._set_font_style('', 10)
        prepared_text = self._prepare_text(body)
        self.multi_cell(0, 5, prepared_text) # Use multi_cell for wrapping
        self.ln(2)

def generate_pdf(selected_articles):
    """Generates a PDF document from selected articles."""
    if not selected_articles:
        return None

    pdf = PDF() # Instantiation will try to load font and set pdf.font_loaded flag
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    for article in selected_articles:
        pdf.chapter_title(article.get('title', 'No Title'))

        pdf._set_font_style('I', 9) # Use helper for metadata font

        # Use helper to prepare text for metadata, applying encoding if needed
        url_text = pdf._prepare_text(f"URL: {article.get('url', 'N/A')}")
        pdf.cell(0, 5, url_text, ln=1)
        date_text = pdf._prepare_text(f"Date: {article.get('publication_date', 'N/A')}")
        pdf.cell(0, 5, date_text, ln=1)
        source_text = pdf._prepare_text(f"Source: {article.get('source', 'N/A')}")
        pdf.cell(0, 5, source_text, ln=1)
        pdf.ln(3)

        # chapter_body calls _prepare_text internally
        pdf.chapter_body("Summary:")
        pdf.chapter_body(article.get('summary', 'No summary available.'))
        pdf.ln(10) # Add space between articles

    # Output PDF as bytes
    try:
        # Fix: Ensure we're returning bytes, not bytearray
        pdf_output = pdf.output(dest='S')
        # Convert to bytes if it's not already
        if isinstance(pdf_output, bytearray):
            pdf_output = bytes(pdf_output)
        return pdf_output
    except Exception as e:
         logging.error(f"Error generating PDF output: {e}", exc_info=True)
         st.error(f"Failed to generate PDF: {e}")
         return None

# --- Streamlit App ---
def run_streamlit_app():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.write("Fetches articles from BBC News, filters for AI topics using Gemini, and allows PDF export.")

    # Initialize Database
    try:
        init_db()
    except Exception as e:
        st.error(f"Fatal Error: Could not initialize database. Check logs. Error: {e}")
        st.stop()

    # --- Sidebar Actions ---
    st.sidebar.header("Actions")
    yesterday = date.today() - timedelta(days=1)
    target_date = st.sidebar.date_input("Select Date for Articles", yesterday)
    
    # Add news source selection dropdown
    selected_source = st.sidebar.selectbox(
        "Select BBC News Section",
        options=list(BBC_SECTIONS.keys()),
        index=0  # Default to BBC Innovation
    )
    selected_url = BBC_SECTIONS[selected_source]
    
    # Add option to update existing articles
    update_existing = st.sidebar.checkbox("Update existing articles", value=False, 
                                        help="If checked, articles with the same URL will be updated instead of skipped")
    
    if st.sidebar.button("1. Fetch & Store Articles for Selected Date"):
        with st.spinner(f"Fetching articles from {selected_source} for {target_date}..."):
            try:
                # Pass the selected URL and source name to the fetch_articles function
                raw_articles = fetch_articles(news_url=selected_url, source_name=selected_source)
                if raw_articles is not None:
                    articles_for_date = filter_articles_by_date(raw_articles, target_date)
                    if articles_for_date:
                        # Pass the update_existing parameter to store_articles
                        count = store_articles(articles_for_date, update_existing)
                        st.sidebar.success(f"Fetched {len(articles_for_date)} articles for {target_date}. Added or updated {count} articles.")
                    else:
                        st.sidebar.warning(f"No articles found on {selected_source} for {target_date}.")
                else:
                    st.sidebar.error(f"Failed to fetch articles from {selected_source}.")
            except Exception as e:
                 st.sidebar.error(f"Error during fetch/store: {e}")
                 logging.error(f"Error during fetch/store: {e}", exc_info=True)

    api_key_present = bool(os.environ.get("GEMINI_API_KEY"))

    if st.sidebar.button("2. Run AI Check on Unprocessed Articles", disabled=not api_key_present):
         if not api_key_present:
              st.sidebar.error("GEMINI_API_KEY not found in .env file or environment. Cannot run AI check.")
         else:
            with st.spinner("Running AI theme check on articles in database... This may take time."):
                try:
                    processed, identified = process_articles_for_ai_theme()
                    st.sidebar.success(f"AI Check Complete. Processed: {processed}, Identified as AI: {identified}")
                    try:
                        st.rerun()
                    except AttributeError:
                        st.experimental_rerun()
                except Exception as e:
                     st.sidebar.error(f"Error during AI check: {e}")
                     logging.error(f"Error during AI check: {e}", exc_info=True)

    if not api_key_present:
         st.sidebar.warning("Set GEMINI_API_KEY in a `.env` file to enable AI checking.")

    st.sidebar.markdown("---")
    st.sidebar.header("Display AI Articles")
    display_date = st.sidebar.date_input("Show AI articles published on:", target_date)

    # --- Main Area: Display AI Articles ---
    st.header(f"AI-Related Articles for {display_date}")

    try:
        ai_articles = get_ai_articles(target_date=display_date)
    except Exception as e:
        st.error(f"Error fetching articles from database: {e}")
        ai_articles = []

    if not ai_articles:
        st.info(f"No AI-related articles found in the database for {display_date}. Try fetching/checking first.")
    else:
        st.write(f"Found {len(ai_articles)} AI-related articles for {display_date}.")

        # Use session state for checkboxes
        if 'selected_articles' not in st.session_state:
             # Initialize state based on currently displayed articles if state is empty
             st.session_state.selected_articles = {article['id']: True for article in ai_articles}
        else:
             # Update state: Keep existing selections for displayed items, add new ones, remove old ones
             current_ids = {article['id'] for article in ai_articles}
             # Remove IDs not currently displayed
             st.session_state.selected_articles = {
                 id: selected for id, selected in st.session_state.selected_articles.items() if id in current_ids
             }
             # Add any new articles (default to True) that weren't in the state before
             for article in ai_articles:
                 if article['id'] not in st.session_state.selected_articles:
                     st.session_state.selected_articles[article['id']] = True

        articles_to_export = []

        for idx, article in enumerate(ai_articles):
            article_id = article['id']
            checkbox_key = f"select_{article_id}_{display_date}"

            # Define the callback function correctly
            def toggle_selection(art_id):
                current_val = st.session_state.selected_articles.get(art_id, True)
                st.session_state.selected_articles[art_id] = not current_val

            is_selected = st.checkbox(
                f"Select Article {idx+1}",
                value=st.session_state.selected_articles.get(article_id, True),
                key=checkbox_key,
                on_change=toggle_selection, # Pass the function itself
                args=(article_id,) # Pass the article_id to the callback
            )

            st.subheader(article['title'])
            st.markdown(f"**URL:** [{article['url']}]({article['url']})")
            st.markdown(f"**Date:** {article['publication_date']}")
            st.markdown(f"**Source:** {article['source']}")
            with st.expander("Show Summary"):
                st.write(article.get('summary', 'No summary available.'))
            st.markdown("---")

            # Check the session state *after* the checkbox is drawn and potentially changed
            if st.session_state.selected_articles.get(article_id, False): # Check the current state
                articles_to_export.append(article)


        # --- PDF Generation Button ---
        if articles_to_export:
             st.markdown("---")
             st.subheader("Export Selected Articles")

             if st.button("Generate PDF from Selection"):
                 with st.spinner("Generating PDF..."):
                     pdf_data = generate_pdf(articles_to_export)
                     if pdf_data:
                         st.download_button(
                             label="Download PDF Report",
                             data=pdf_data,
                             file_name=f"ai_news_{display_date}.pdf",
                             mime="application/pdf"
                         )
                     else:
                         st.error("Could not generate PDF.")
        elif ai_articles:
             st.warning("Select at least one article using the checkboxes above to generate a PDF.")

# --- Main execution ---
if __name__ == '__main__':
    run_streamlit_app()