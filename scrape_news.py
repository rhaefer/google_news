import requests
import ollama
import supabase
import os
from datetime import datetime, timedelta
import re
from dateutil import parser

# ✅ Initialize Supabase connection
SUPABASE_URL = "https://nyngjfovyljrzeqnetgy.supabase.co"  # Replace with your Supabase project URL
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im55bmdqZm92eWxqcnplcW5ldGd5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczMDgyNzQ4MCwiZXhwIjoyMDQ2NDAzNDgwfQ.3X_jAe8LdkqnBHTyIJyh5Y7_YL5KlxQDhfIup9FKh7c"  # Replace with your Supabase Key
supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

# ✅ SerpAPI configuration
SERPAPI_KEY = "0c1c9a768d8747428727639c9318efcf7ae832a0bb19c8271f5e51471739e869"

# ✅ Define major news sources (Higher popularity boost)
TOP_NEWS_SOURCES = ["nytimes.com", "bbc.com", "forbes.com", "washingtonpost.com", "theguardian.com"]

# ✅ Define trending keywords (Boost if found in snippet)
TRENDING_KEYWORDS = ["trending", "viral", "most read", "breaking news", "popular", "record high"]


def convert_relative_date(relative_date):
    """Convert relative timestamps (e.g., '2 weeks ago') to actual dates."""
    if not relative_date:
        return None  

    try:
        return parser.parse(relative_date).strftime('%Y-%m-%d')
    except Exception:
        pass  

    match = re.match(r"(\d+) (day|week|month|year)s? ago", relative_date)
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        if unit == "day":
            actual_date = datetime.utcnow() - timedelta(days=amount)
        elif unit == "week":
            actual_date = datetime.utcnow() - timedelta(weeks=amount)
        elif unit == "month":
            actual_date = datetime.utcnow() - timedelta(days=amount * 30)
        elif unit == "year":
            actual_date = datetime.utcnow() - timedelta(days=amount * 365)
        return actual_date.strftime('%Y-%m-%d')

    return None  


def fetch_google_news():
    """Fetch top sauna-related Google News articles from the past week using SerpAPI and estimate popularity."""
    one_week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')

    params = {
        "q": "sauna",
        "hl": "en",
        "gl": "us",
        "api_key": SERPAPI_KEY,
        "tbm": "nws",
        "tbs": f"cdr:1,cd_min:{one_week_ago}"  
    }

    response = requests.get("https://serpapi.com/search", params=params)
    data = response.json()

    articles = []
    for result in data.get("news_results", []):
        formatted_date = convert_relative_date(result.get("date"))
        if not formatted_date:
            formatted_date = datetime.utcnow().strftime('%Y-%m-%d')

        snippet = result.get("snippet", "").lower()

        # ✅ 1. Assign Base Popularity Score
        popularity_score = 0  

        # ✅ 2. Boost for Major News Sources
        if any(source in result["link"] for source in TOP_NEWS_SOURCES):
            popularity_score += 5  

        # ✅ 3. Boost for Trending Keywords
        if any(kw in snippet for kw in TRENDING_KEYWORDS):
            popularity_score += 3  

        # ✅ 4. Boost for Recency (More points for newer articles)
        days_old = (datetime.utcnow() - datetime.strptime(formatted_date, "%Y-%m-%d")).days
        if days_old <= 1:
            popularity_score += 4  # Recent articles get highest boost
        elif days_old <= 3:
            popularity_score += 2  
        elif days_old <= 7:
            popularity_score += 1  

        # ✅ 5. Boost for Longer Snippets (More in-depth articles)
        if len(snippet) > 150:
            popularity_score += 2  
        elif len(snippet) > 80:
            popularity_score += 1  

        articles.append({
            "title": result["title"],
            "link": result["link"],
            "source": result["source"],
            "date": formatted_date,
            "snippet": snippet,
            "popularity_score": popularity_score  
        })

    # ✅ Sort by popularity score before returning
    sorted_articles = sorted(articles, key=lambda x: x["popularity_score"], reverse=True)

    return sorted_articles[:50]  


def store_news_in_supabase(articles):
    """Store summarized sauna news articles in Supabase."""
    for article in articles:
        summary = article["snippet"][:200]  # Take first 200 characters

        # ✅ Debugging: Print what’s being inserted
        print(f"Storing: {article['title']} | Popularity: {article['popularity_score']}")

        existing_article = supabase_client.table("sauna_news").select("title").eq("title", article["title"]).execute()
        if existing_article.data:
            print(f"Skipping duplicate: {article['title']}")
            continue

        response = supabase_client.table("sauna_news").insert({
            "title": article["title"],
            "summary": summary,
            "link": article["link"],
            "source": article["source"],
            "published_date": article["date"],
            "popularity_score": article["popularity_score"]
        }).execute()

        if response.data:
            print(f"✅ Stored: {article['title']} (Popularity Score: {article['popularity_score']})")
        else:
            print(f"❌ Failed to store: {article['title']}")


def generate_newsletter_section():
    """Fetch top 3 articles from Supabase and format them for the newsletter."""
    response = supabase_client.table("sauna_news").select("*").order("popularity_score", desc=True).limit(3).execute()

    if not response.data:
        return "<p>No trending sauna news this week. Stay tuned for the next update!</p>"

    content = "<h1>🔥 Trending Sauna News 🔥</h1>\n\n"

    for article in response.data:
        content += f'<h2>{article["title"]}</h2>\n'
        content += f'<p>{article["summary"]}</p>\n'
        content += f'<p><a href="{article["link"]}" target="_blank">Read more...</a></p>\n'
        content += "<hr>\n"

    return content


if __name__ == "__main__":
    news_articles = fetch_google_news()
    
    # ✅ Debugging: Print fetched articles
    for article in news_articles:
        print(f"Fetched: {article['title']} | Popularity: {article['popularity_score']}")

    store_news_in_supabase(news_articles)
    #newsletter_content = generate_newsletter_section()
    #print(newsletter_content)
