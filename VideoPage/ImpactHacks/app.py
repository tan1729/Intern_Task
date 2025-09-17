from flask import Flask, render_template, request, jsonify
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from deep_translator import GoogleTranslator
import re
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# YouTube API details
API_KEY = "AIzaSyCxFXcJ76MesUkwlRxBoIX15qGLF0ILljA"  #Use your API Keys
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_STATS_URL = "https://www.googleapis.com/youtube/v3/videos"

# Dictionary of supported Northeast Indian languages
LANGUAGES = {
    "as": "Assamese",
    "mni": "Meiteilon (Manipuri)",
    "lus": "Mizo"
}

def get_top_video(search_query):
    """Fetch top 20 videos and choose the one with the best like-to-view ratio."""
    logger.info(f"Searching for videos with query: {search_query}")
    search_params = {
        "part": "snippet",
        "q": search_query,
        "type": "video",
        "maxResults": 20,
        "key": API_KEY
    }
    response = requests.get(YOUTUBE_SEARCH_URL, params=search_params).json()
    video_list = []
   
    if "items" in response:
        for item in response["items"]:
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            stats_params = {"part": "statistics", "id": video_id, "key": API_KEY}
            stats_data = requests.get(YOUTUBE_VIDEO_STATS_URL, params=stats_params).json()
            if "items" in stats_data and len(stats_data["items"]) > 0:
                stats = stats_data["items"][0]["statistics"]
                views = int(stats.get("viewCount", 1))
                likes = int(stats.get("likeCount", 1))
                ratio = likes / views if views > 0 else 0
                video_list.append((video_id, title, ratio))
   
    if not video_list:
        logger.warning("No videos found for the query")
        return None
   
    best_video = max(video_list, key=lambda x: x[2])
    logger.info(f"Selected video ID: {best_video[0]}, Title: {best_video[1]}")
    return {"id": best_video[0], "title": best_video[1]}

def srt_time_to_seconds(time_str):
    """Convert SRT time format to seconds."""
    h, m, s = time_str.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

def fetch_transcript(video_id, target_lang="as"):
    """Fetch transcript, convert it into SRT format, and translate it."""
    logger.info(f"Fetching transcript for video ID: {video_id}, target language: {target_lang}")
    try:
        transcript_list = YouTubeTranscriptApi.get_transcripts([video_id])
        if not transcript_list:
            return "Transcript not available for this video."
        transcript = transcript_list[video_id]
        
        logger.info(f"Successfully retrieved transcript with {len(transcript)} entries")
    except Exception as e:
        logger.error(f"Error getting transcript: {str(e)}")
        return "Transcript not available for this video."
    
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"
    
    srt_text = ""
    
    # Check if language is supported
    if target_lang not in LANGUAGES:
        logger.warning(f"Unsupported language code: {target_lang}, defaulting to Assamese")
        target_lang = "as"  # Default to Assamese if invalid
    
    for i, entry in enumerate(transcript, 1):
        start_time = format_time(entry['start'])
        end_time = format_time(entry['start'] + entry['duration'])
        
        # Translate each caption line
        try:
            translated_text = GoogleTranslator(source="auto", target=target_lang).translate(entry["text"])
            logger.debug(f"Translated text: {translated_text}")
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            # Fallback if translation fails
            translated_text = entry["text"] + " (Translation failed)"
        
        srt_text += f"{i}\n{start_time} --> {end_time}\n{translated_text}\n\n"
   
    return srt_text

# Groq API Configuration
GROQ_API_KEY = "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"  # Replace with your actual API key
GROQ_API_URL = "https://api.groq.com/v1/chat/completions"



# Function to fetch YouTube transcript
def get_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcripts([video_id])
        if not transcript_list:
            return None
        transcript = transcript_list[video_id]
        transcript_text = ' '.join([item['text'] for item in transcript])
        return transcript_text.strip()
    except Exception as e:
        logger.error(f"Error fetching transcript: {e}")
        return None

# Function to get summary from Groq API
def generate_summary(transcript_text):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "You are an AI assistant that summarizes an educational YouTube video transcript. Provide a summary using the transcript which can be used by the user for revision such that it goes over all the important concepts."},
            {"role": "user", "content": f"Summarize the following transcript: {transcript_text}"}
        ],
        "max_tokens": 1024
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"].strip()
        else:
            logger.error("Groq API response missing choices or empty choices list")
            return "Summary not available."
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
    except Exception as e:
        logger.error(f"Error calling Groq API: {e}")
    return "Summary not available."


def translate_large_text(texts, source_lang="en", target_lang="as"):
    """Translates large text chunks while maintaining SRT format"""
    translator = GoogleTranslator(source=source_lang, target=target_lang)
    translated_text = translator.translate(texts)
    return translated_text

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    query = request.form.get("query")
    logger.info(f"Search request received with query: {query}")
    top_video = get_top_video(query)
    if not top_video:
        return jsonify({"error": "No videos found."})
    return jsonify(top_video)

@app.route("/transcript", methods=["POST"])
def transcript():
    video_id = request.form.get("video_id")
    language = request.form.get("language", "as")
    logger.info(f"Transcript request received for video ID: {video_id}, language: {language}")
    srt_text = fetch_transcript(video_id, language)
    return jsonify({"transcript": srt_text})

@app.route("/video/<video_id>")
def video_page(video_id):
    logger.info(f"Rendering video page for video_id: {video_id}")
    # Fetch video title
    video_params = {
        "part": "snippet",
        "id": video_id,
        "key": API_KEY
    }
    response = requests.get(YOUTUBE_VIDEO_STATS_URL, params=video_params)
    if response.status_code != 200 or not response.json().get("items"):
        logger.error(f"Video not found for ID: {video_id}")
        return "Video not found", 404
    video_title = response.json()["items"][0]["snippet"]["title"]
    logger.info(f"Video title: {video_title}")

    # Fetch transcript in default language
    transcript_text = fetch_transcript(video_id, "as")
    logger.info(f"Transcript text length: {len(transcript_text)}")

    # Generate summary
    transcript_plain = get_transcript(video_id)
    logger.info(f"Plain transcript: {transcript_plain[:100] if transcript_plain else 'None'}")
    summary = generate_summary(transcript_plain) if transcript_plain else "Summary not available."
    logger.info(f"Generated summary: {summary}")

    # Translate summary to default language
    try:
        translated_summary = translate_large_text(summary, "en", "as") if summary != "Summary not available." else summary
        logger.info(f"Translated summary: {translated_summary}")
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        translated_summary = summary

    return render_template("video.html", video_id=video_id, video_title=video_title, transcript=transcript_text, summary=translated_summary)

@app.route("/test_summary/<video_id>")
def test_summary(video_id):
    transcript_plain = get_transcript(video_id)
    if not transcript_plain:
        return "No transcript available"
    summary = generate_summary(transcript_plain)
    return f"Summary: {summary}"

if __name__ == "__main__":
    app.run(debug=True)
