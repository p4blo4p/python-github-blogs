import os
import xml.etree.ElementTree as ET
from datetime import datetime
from core.logger import logger

def generate_sitemap(posts, output_dir="docs"):
    """
    Genera sitemap.xml basado en los posts generados.
    Asume que los posts están en output_dir/titulo.html
    """
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    
    # URL base (cámbiala por la tuya o pásala como variable)
    base_url = "https://p4blo4p.github.io/python-github-blogs/" 
    
    # Añadir la home
    url = ET.SubElement(urlset, "url")
    ET.SubElement(url, "loc").text = base_url
    ET.SubElement(url, "lastmod").text = datetime.now().strftime("%Y-%m-%d")
    ET.SubElement(url, "changefreq").text = "daily"
    
    for post in posts:
        # post['slug'] debe existir en tu estructura de datos
        full_url = f"{base_url}blog/{post['slug']}.html"
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = full_url
        ET.SubElement(url, "lastmod").text = post['date']
        ET.SubElement(url, "changefreq").text = "weekly"
        
    tree = ET.ElementTree(urlset)
    tree.write(os.path.join(output_dir, "sitemap.xml"), encoding='utf-8', xml_declaration=True)
    logger.info("Sitemap.xml generado exitosamente.")

def generate_rss(posts, output_dir="docs"):
    """
    Genera rss.xml
    """
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    ET.SubElement(channel, "title").text = "AutoBlog Engine PRO MAX"
    ET.SubElement(channel, "link").text = "https://p4blo4p.github.io/python-github-blogs/"
    ET.SubElement(channel, "description").text = "Blog generado por IA"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
    
    for post in posts:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = post['title']
        ET.SubElement(item, "link").text = f"https://p4blo4p.github.io/python-github-blogs/blog/{post['slug']}.html"
        ET.SubElement(item, "description").text = post['content'][:200] + "..." # Resumen
        ET.SubElement(item, "pubDate").text = post['date']
        
    tree = ET.ElementTree(rss)
    tree.write(os.path.join(output_dir, "rss.xml"), encoding='utf-8', xml_declaration=True)
    logger.info("RSS.xml generado exitosamente.")