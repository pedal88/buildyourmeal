import requests
from bs4 import BeautifulSoup

class WebScraper:
    def scrape_url(self, url):
        """
        Fetches a URL and extracts the main text content and a hero image.
        Returns: { 'text': str, 'image_url': str }
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # --- 1. Extract Text ---
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get text
            text = soup.get_text(separator=' ', strip=True)
            # Limit text length to avoid token limits (arbitrary cap, e.g., 20k chars is usually enough for a blog post)
            text = text[:20000]

            # --- 2. Extract Hero Image ---
            # Priority 1: Open Graph Image
            og_image = soup.find("meta", property="og:image")
            image_url = None
            if og_image and og_image.get("content"):
                image_url = og_image["content"]
            
            # Priority 2: First large image (heuristic)
            if not image_url:
                images = soup.find_all('img')
                for img in images:
                    src = img.get('src')
                    if src and src.startswith('http'):
                        # Basic heuristic: check if it looks like a content image
                        # In a real app, we'd check dimensions, but for now just taking the first valid http image
                        image_url = src
                        break
            
            return {
                "text": text,
                "image_url": image_url
            }

        except Exception as e:
            print(f"Scraper Error: {e}")
            raise e
