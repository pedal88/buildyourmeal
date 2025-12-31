from services.web_scraper_service import WebScraper

def test_url():
    url = "https://www.matprat.no/oppskrifter/gjester/waldorfsalat/"
    print(f"Testing URL: {url}")
    
    try:
        scraper = WebScraper()
        data = scraper.scrape_url(url)
        
        print(f"Status: Success")
        print(f"Text Length: {len(data['text'])}")
        print(f"Image URL: {data['image_url']}")
        print("-" * 20)
        print("First 500 chars of text:")
        print(data['text'][:500])
        print("-" * 20)
        
    except Exception as e:
        print(f"Status: Failed")
        print(f"Error: {e}")

if __name__ == "__main__":
    test_url()
