import feedparser
import spacy
import google.generativeai as genai
import os
from flask import Flask, render_template, request, jsonify
import smtplib
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask_mail import Mail, Message
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__) 
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Use your email provider's SMTP server
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'your-email-password'  # Use App Password for security
app.config['MAIL_DEFAULT_SENDER'] = 'your-email@gmail.com'

mail = Mail(app)

# Load NLP model
nlp = spacy.load("en_core_web_sm")


# Configure Gemini API Key
genai.configure(api_key="gem-key.txt")

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

app = Flask(__name__)

# Store user preferences in-memory (For simplicity; Use a database for production)
user_preferences = {}

# Fetch articles
def fetch_articles():
    articles = []
    for category, urls in rss_feeds.items():
        for url in urls:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title if hasattr(entry, 'title') else "Untitled Article"
                summary_text = entry.summary if hasattr(entry, 'summary') else title
                articles.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": summary_text,  # Use title if summary is missing
                    "category": category
                })
    return articles


# Categorize articles
def classify_article(article):
    doc = nlp(article["title"] + " " + article["summary"])
    scores = {persona: sum(1 for word in persona_keywords[persona] if word.lower() in doc.text.lower())
              for persona in persona_keywords}
    return max(scores, key=scores.get)

# Summarize articles using Gemini API
def summarize_article(title, article_text):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt_text = f"Summarize this article in 2 sentences:\nTitle: {title}\nContent: {article_text}"
        response = model.generate_content(f"Summarize this article in 2 sentences: {prompt_text}")
        print("API Response:", response)  # Debugging: See what Gemini returns
        return response.candidates[0]['content'].strip() if response and response.candidates else "⚠️ Summary unavailable."
      
    except Exception as e:
        print("Error:", str(e))
        return "⚠️ Summary unavailable."


# Generate structured newsletter
def generate_newsletter(persona, articles):
    newsletter = f"# Personalized Newsletter for {persona}\n\n"
    if not articles:
        newsletter += "_No articles found for you today._"
        return newsletter

    newsletter += "## Top Stories\n"
    for article in articles:
        newsletter += f"- **{article['title']}**\n  *{article['summary']}*\n  [Read more]({article['link']})\n\n"
    return newsletter


def generate_newsletter_content(user_id):
    user_data = user_preferences.get(user_id, {})
    user_interests = user_data.get("interests", [])

    print("DEBUG: User interests:", user_interests)

    articles = fetch_articles()
    print("DEBUG: Fetched articles:", articles)

    # Filter articles based on user interests
    filtered_articles = [article for article in articles if article["category"] in user_interests]
    print("DEBUG: Filtered articles:", filtered_articles)

    if not filtered_articles:
        return "# Your Personalized Newsletter\n\n_No relevant articles found for you today._"

    # Summarize articles
    for article in filtered_articles:
        article["summary"] = summarize_article(article["title"], article["summary"])

    # Organize articles by category
    categorized_articles = {}
    for article in filtered_articles:
        if article["category"] not in categorized_articles:
            categorized_articles[article["category"]] = []
        categorized_articles[article["category"]].append(article)

    # Generate Markdown content
    newsletter_md = "# 📢 Your Personalized Newsletter\n\n"
    
    # ✨ Summary Section
    top_articles = filtered_articles[:3]  # Pick top 3 articles for a concise summary
    newsletter_md += "## 🔥 Top Stories\n"
    for article in top_articles:
        newsletter_md += f"- **[{article['title']}]({article['link']})**\n  *{article['summary']}*\n\n"

    # ✨ Category-wise Organization
    for category, articles in categorized_articles.items():
        newsletter_md += f"## {category.capitalize()}\n\n"
        for article in articles:
            newsletter_md += f"- **[{article['title']}]({article['link']})**\n  *{article['summary']}*\n\n"

    print("DEBUG: Final Markdown Newsletter:", newsletter_md)
    
    # Save Markdown to a file
    file_path = f"newsletters/{user_id}_newsletter.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(newsletter_md)

    return file_path  # Return the saved file path

    
@app.route('/set_preferences', methods=['POST'])
def set_preferences():
    full_name = request.form.get("full_name")
    email = request.form.get("email")
    interests = request.form.getlist("interests")
    frequency = request.form.get("frequency")

    # Debugging: Check if email is received
    print("Received Email:", email)

    if not email:
        return jsonify({"message": "Error: Email is required!", "redirect": None})

    user_id = email.strip().lower()  
    user_preferences[user_id] = {
        "name": full_name,
        "interests": interests,
        "frequency": frequency
    }

    # Generate newsletter content
    newsletter_content = generate_newsletter_content(user_id)

    # Send Email
    send_newsletter_email(email, full_name, newsletter_content)

    return jsonify({"message": "Subscription successful! Check your email!", "redirect": f"/newsletter/{user_id}"})


def send_newsletter_email(email, full_name, newsletter_file):
    try:
        print("DEBUG: Newsletter file path:", newsletter_file)

        sender_email = os.getenv("EMAIL_USER")  
        sender_password = os.getenv("EMAIL_PASS")  

        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = email
        msg["Subject"] = f"Your Personalized Newsletter, {full_name}!"

        # Attach the Markdown file
        with open(newsletter_file, "r", encoding="utf-8") as f:
            newsletter_content = f.read()

        msg.attach(MIMEText(newsletter_content, "plain"))

        # Attach the file itself
        with open(newsletter_file, "rb") as attachment:
            mime_type, _ = mimetypes.guess_type(newsletter_file)
            mime_type = mime_type or "text/markdown"
            attachment_part = MIMEText(attachment.read().decode("utf-8"), "plain")
            attachment_part.add_header("Content-Disposition", f"attachment; filename={newsletter_file}")
            msg.attach(attachment_part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, msg.as_string())
        server.quit()

        print(f"Newsletter successfully sent to {email}")

    except Exception as e:
        print("Error sending email:", str(e))



# Routes

@app.route('/form')
def form():
    return render_template("form.html")  # Ensure form.html exists in the templates folder

@app.route('/')
def home():
    return render_template('index.html')



@app.route('/newsletter/<user_id>')
def newsletter(user_id):
    return generate_newsletter(user_id)

if __name__ == '__main__':
    app.run(debug=True)
    
