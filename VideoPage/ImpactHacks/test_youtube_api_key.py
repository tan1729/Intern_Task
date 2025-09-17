import requests

API_KEY = "AIzaSyCxFXcJ76MesUkwlRxBoIX15qGLF0ILljA"  # Replace with your new API key if needed
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

def test_youtube_api_key():
    params = {
        "part": "snippet",
        "q": "test",
        "type": "video",
        "maxResults": 1,
        "key": API_KEY
    }
    response = requests.get(YOUTUBE_SEARCH_URL, params=params)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

if __name__ == "__main__":
    test_youtube_api_key()
