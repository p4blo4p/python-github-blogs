import requests
from bs4 import BeautifulSoup
import feedparser
from core.logger import logger

def get_github_trending(language=""):
    """
    Obtiene los repositorios en tendencia de GitHub.
    """
    url = f"https://github.com/trending/{language}" if language else "https://github.com/trending"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        repos = []
        articles = soup.select('article.Box-row')
        
        for article in articles:
            try:
                title_tag = article.select_one('h2 a')
                desc_tag = article.select_one('p')
                stars_tag = article.select_one('a[href*="/stargazers"]')
                
                title = title_tag.get_text().strip().replace("\n", "").replace(" ", "")
                url_repo = "https://github.com" + title_tag['href']
                description = desc_tag.get_text().strip() if desc_tag else "Sin descripción"
                stars = stars_tag.get_text().strip() if stars_tag else "0"
                
                repos.append({
                    "title": title,
                    "url": url_repo,
                    "description": description,
                    "stars": stars
                })
            except Exception as e:
                logger.warning(f"Error parseando un repo: {e}")
                continue
                
        return repos[:5] # Retornar top 5
    except Exception as e:
        logger.error(f"Error obteniendo GitHub Trending: {e}")
        return []

def get_external_rss(feed_url, limit=3):
    """
    Lee noticias de un RSS feed externo.
    """
    try:
        feed = feedparser.parse(feed_url)
        entries = []
        for entry in feed.entries[:limit]:
            entries.append({
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get('summary', '')
            })
        return entries
    except Exception as e:
        logger.error(f"Error leyendo RSS {feed_url}: {e}")
        return []