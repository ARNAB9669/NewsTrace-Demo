📰 NewsTrace — Intelligent Journalist Ecosystem Visualizer

Team: Arnab BiswasHackathon: Hack of Thrones (NASA Space Apps aligned theme)Category: AI + Web Scraping + Data VisualizationStatus: Fully Functional Local Prototype (Backend + Frontend)

🌍 Overview

NewsTrace is an intelligent system designed to autonomously detect, extract, and visualize journalist ecosystems of any media outlet.Given the name of a news outlet (e.g., The Hindu, BBC, CNN), the system:

Finds the official website in real time (Stage 0).

Scrapes journalist data (authors, beats, articles, etc.) from public sources (Stage 1).

Builds analytics and relationships between journalists and topics (Stage 2–3).

Visualizes the entire network interactively on a dashboard (Stage 4).

No hardcoded URLs or pre-stored outlet mappings — the scraper intelligently detects the official domain dynamically.

🧠 System Architecture

Frontend (HTML + JS + Chart.js + vis-network)
        │
        ▼
Flask Backend (app.py)
        │
        ▼
Smart Scraper (scrapper.py)
   ├─ Stage 0: Website Detection
   ├─ Stage 1: Journalist Extraction
   ├─ Stage 2: Topic/Beat Categorization
   ├─ Stage 3: Network Graph Generation
   └─ Stage 4: JSON Output → Visualization

Frontend:A dynamic dashboard built with vanilla JS, Chart.js, and vis-network.It renders a table of journalists, a bar graph of top beats, and an interactive topic network.

Backend (Flask):Serves static files and connects the frontend to the Python scraper.Exposes a single route /api/scrape that triggers live scraping.

Scraper:Modular, resilient, and progressively writes partial data to data.json to ensure fault tolerance.It includes fallback logic for detection, robots.txt compliance, and NLP-style beat normalization.

⚙️ Setup & Execution

1. Clone Repository

git clone https://github.com/arnabbiswas/NewsTrace.git
cd NewsTrace

2. Install Dependencies

pip install flask beautifulsoup4 requests

3. Run Backend

cd Backend
python3 app.py

4. Open Frontend

Open your browser and visit:

http://127.0.0.1:5000

5. Enter an Outlet Name

Example:

The Hindu

You’ll see live scraping begin — followed by table, chart, and network visualization updates.

🧩 Functional Stages

Stage 0: Real-Time Website Detection

Automatically detects the official website of the entered outlet using heuristic domain generation + DuckDuckGo/Bing fallback.

No pre-stored URL maps — true real-time lookup.

Stage 1: Journalist Ecosystem Extraction

Crawls discovered domain for /news/, /author/, /article/, and similar paths.

Extracts metadata:

Journalist name

Beat or section

Latest article title

Article count

Ensures at least 30 profiles are collected.

Stage 2: Intelligence Layer

Performs lightweight NLP-style keyword extraction and beat normalization.

Categorizes authors by topic frequency and publication activity.

Highlights top contributors dynamically.

Stage 3: Network and Relationship Analysis

Builds a bipartite graph (journalists ↔ topics).

Visualizes clusters of authors covering similar domains using vis-network.

Stage 4: Output and Visualization

Real-time frontend rendering with:

Interactive table view

Top Beats bar chart

Graph of Journalist → Topic

Loader animation for scraping progress

CSV/JSON export-ready through data.json.

🗂️ Output Format

data.json structure:

{
  "outlet_name": "The Hindu",
  "website": "https://www.thehindu.com",
  "profiles": [
    {
      "name": "Suhasini Haidar",
      "beat": "World",
      "latest_article": "Japan’s new PM commits to higher defence spend",
      "articles_count": 5,
      "publication_date": "2025-10-24"
    }
  ]
}

🚀 Deployment Notes

Due to recent limitations of free dynamic backend hosting services (e.g., Render, Railway, Cyclic),this project is currently designed as a fully offline, local prototype.Deployment-ready architecture, however, supports containerization:

docker build -t newstrace .
docker run -p 5000:5000 newstrace

Frontend can then be hosted on Vercel, Netlify, or GitHub Pages,while the backend connects to a cloud VM or Render service.

🔊 Highlights

✅ Fully functional across all stages (0–4)✅ 100% Python-based autonomous scraper✅ No hardcoded outlets✅ Partial data saving to avoid timeouts✅ Visual analytics dashboard✅ Future-ready for distributed scraping + graph databases

🧑‍💻 Developer Notes

Built from scratch in under two weeks.

Code is modular, commented, and optimized for expansion.

Ready for Stage 5 extensions (cross-outlet overlap, clustering, etc.).

📊 Sample Output (From “The Hindu”)

Name

Beat

Latest Article

Article Count

The Hindu Bureau

Breaking

Public can adopt animals...

66

Purnima Sah

Breaking

Doctor’s suicide in Satara...

14

Peerzada Ashiq

Breaking

Judicial panel to begin...

13

Suhasini Haidar

World

Japan’s new PM commits...

5

Reuters

World

U.S. to escalate military...

6

📚 Future Enhancements

🔍 Integrate keyword embeddings via SLM or TF-IDF for deeper topic clustering.

🗾 Add persistent database (Neo4j / SQLite).

☁️ Deploy backend on serverless infrastructure for real-time API use.

🏁 Conclusion

NewsTrace demonstrates the full pipeline from real-time outlet discovery → journalist ecosystem extraction → interactive visualization, satisfying every milestone of the challenge.The system provides a scalable base for media analysis, misinformation tracking, or journalist influence mapping.

“If journalism is the first draft of history, NewsTrace is the map behind it.”

