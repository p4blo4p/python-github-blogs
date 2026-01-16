import frontmatter
import markdown
from datetime import datetime

class ContentParser:
    def __init__(self):
        self.md = markdown.Markdown(extensions=['extra', 'codehilite', 'toc'])

    def parse(self, raw_md, filename):
        post = frontmatter.loads(raw_md)
        metadata = post.metadata
        
        # Fallbacks
        title = metadata.get('title', filename.replace('.md', ''))
        date_str = metadata.get('date', datetime.now().isoformat())
        
        try:
            date_obj = datetime.fromisoformat(date_str)
        except:
            date_obj = datetime.now()

        html_content = self.md.convert(post.content)
        self.md.reset()

        return {
            'title': title,
            'date': date_obj,
            'slug': filename.replace('.md', '.html'),
            'content': html_content,
            'summary': metadata.get('summary', html_content[:200] + "..."),
            'tags': metadata.get('tags', [])
        }