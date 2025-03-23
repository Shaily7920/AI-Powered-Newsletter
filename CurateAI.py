import feedparser
import openai
import spacy
import markdown
import os
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

# Load NLP model
nlp = spacy.load("en_core_web_sm")

# Define RSS feeds
rss_feeds = {
    "technology": ["https://techcrunch.com/feed/", "https://www.wired.com/feed/"],
    "finance": ["https://www.bloomberg.com/feed/", "https://www.coindesk.com/arc/outboundfeeds/rss/"],
    "sports": ["https://www.espn.com/espn/rss/news"],
    "entertainment": ["https://variety.com/feed/", "https://www.billboard.com/feed/"],
    "science": ["https://www.nasa.gov/rss/dyn/breaking_news.rss"]
}

# Define user personas
persona_keywords = {
    "Alex Parker": ["AI", "cybersecurity", "blockchain", "startups", "programming"],
    "Priya Sharma": ["finance", "markets", "fintech", "cryptocurrency", "economics"],
    "Marco Rossi": ["football", "F1", "NBA", "Olympics", "esports"],
    "Lisa Thompson": ["movies", "celebrity", "TV shows", "music", "books"],
    "David Martinez": ["space", "biotech", "physics", "renewable energy"]
}

# OpenAI API Key
openai.api_key_path = "key.txt"

app = Flask('CurateAI',static_folder='static')

# Fetch articles
def fetch_articles():
    articles = []
    for category, urls in rss_feeds.items():
        for url in urls:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.summary if "summary" in entry else "",
                    "category": category
                })
    return articles

# Categorize articles
def classify_article(article):
    doc = nlp(article["title"] + " " + article["summary"])
    scores = {persona: sum(1 for word in persona_keywords[persona] if word.lower() in doc.text.lower())
              for persona in persona_keywords}
    return max(scores, key=scores.get)

# Summarize articles using GPT-4
def summarize_article(article_text):
    response = openai.ChatCompletion.create(
        model="gpt-4.5",
        messages=[{"role": "user", "content": f"Summarize this article: {article_text}"}]
    )
    return response["choices"][0]["message"]["content"]

# Generate newsletters
def generate_newsletter(persona, articles):
    newsletter = f"# Personalized Newsletter for {persona}\n\n"
    newsletter += "## Top Stories\n"
    for article in articles:
        newsletter += f"- **{article['title']}**\n  *{article['summary']}*\n  [Read more]({article['link']})\n\n"
    return newsletter

# Flask Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    articles = fetch_articles()
    for article in articles:
        article["assigned_persona"] = classify_article(article)
        article["summary"] = summarize_article(article["summary"])
    
    newsletters = {}
    for persona in persona_keywords.keys():
        persona_articles = [a for a in articles if a["assigned_persona"] == persona]
        newsletters[persona] = generate_newsletter(persona, persona_articles)
        with open(f"newsletters/{persona.replace(' ', '_').lower()}_newsletter.md", "w", encoding="utf-8") as f:
            f.write(newsletters[persona])
    
    return jsonify({"message": "Newsletters Generated!"})

# Scheduler for automation
scheduler = BackgroundScheduler()
scheduler.add_job(func=generate, trigger='interval', hours=24)
scheduler.start()

if __name__ == '__main__':
    os.makedirs("newsletters", exist_ok=True)
    app.run(debug=True)
