# AI News Automation Tool (BBC Innovation)

This Python script automates the process of finding news articles related to Artificial Intelligence (AI) from the BBC Innovation website (`https://www.bbc.com/innovation`), filtering them by date, classifying them using Google Gemini, storing them in a local SQLite database, and providing a simple web interface to review and export selected articles as a PDF.

## Features

*   Connects to BBC Innovation and scrapes articles.
*   Parses article titles, URLs, publication dates, and summaries.
*   Filters articles based on a specific publication date (e.g., yesterday).
*   Uses the Google Gemini API (specifically `gemini-1.5-flash-latest`) to classify articles based on their relevance to AI since OpenAi API are not free.
*   Stores relevant article data in a local SQLite database (`news_articles.db`).
*   Provides a web interface using Streamlit to:
    *   Trigger article fetching and AI classification.
    *   View AI-related articles for a specific date.
    *   Select articles for export.
    *   Generate and download a PDF report of selected articles.
*   Includes basic error handling for web requests, date parsing, API calls, and database operations.

## Prerequisites

*   Python 3.7+
*   Pip (Python package installer)
*   Google Gemini API Key

## Setup

1.  **Clone the repository or download the files:**
    ```bash
    # git clone https://github.com/tomdieu/automation-test
    # cd automation-test
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up Google Gemini API Key:**
    *   Obtain an API key from [Google AI Studio](https://aistudio.google.com/).
    *   Create a file named `.env` in the root directory of the project (where `app.py` is located).
    *   Add the following line to the `.env` file, replacing `YOUR_API_KEY_HERE` with your actual key:
        ```dotenv
        GEMINI_API_KEY=YOUR_API_KEY_HERE
        ```

## How to Run

1.  **Navigate to the project directory** in your terminal.
2.  **Run the Streamlit application:**
    ```bash
    streamlit run app.py
    ```
3.  This will open the web interface in your default browser.

## Usage Workflow (via Streamlit UI)

1.  **Select Date:** Use the date input in the sidebar to choose the publication date you are interested in (defaults to yesterday).
2.  **Fetch & Store:** Click the "1. Fetch & Store Articles for Selected Date" button. The script will scrape BBC Innovation, filter for the selected date, and add any new articles found to the database.
3.  **Run AI Check:** Click the "2. Run AI Check on Unprocessed Articles" button. The script will fetch articles from the database that haven't been checked yet, send their title/summary to Gemini for classification, and update the database. This might take some time depending on the number of articles and API rate limits.
4.  **View AI Articles:** The main panel displays articles marked as AI-related for the date selected in the lower sidebar date input.
5.  **Select & Export:** Check the boxes next to the articles you want to include in the report.
6.  **Generate PDF:** Click the "Generate PDF from Selection" button.
7.  **Download:** Click the "Download PDF Report" button that appears.

## Notes

*   **Web Scraping Fragility:** The script relies on the current HTML structure and `data-testid` attributes of `bbc.com/innovation`. If the website structure changes, the scraping part (`scraper.py`) may need adjustments.
*   **Gemini API Usage:** This script uses the Google Gemini API, which has free tier limits (e.g., requests per minute). The script includes a small delay (`time.sleep(1.1)`) between API calls to help stay within typical free limits, but heavy usage might still exceed them. Check Google's current free tier limits.
*   **AI Accuracy:** The accuracy of the AI theme classification depends on the Gemini model and the quality of the prompt. Summaries are sometimes missing, which might affect accuracy.
*   **Database:** The `news_articles.db` file will be created in the same directory where you run the script.
