import gradio as gr
import requests
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import isodate
import logging
from youtube_transcript_api import YouTubeTranscriptApi

# Configure loggingg
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Keys and Endpoints
GROQ_API_KEY = "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"  # Use secrets in production
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
YOUTUBE_API_KEY = "AIzaSyCxFXcJ76MesUkwlRxBoIX15qGLF0ILljA"  # Use secrets in production
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_STATS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

# Flask app URL - change to ngrok URL if using Gradio share=True
FLASK_URL = "http://127.0.0.1:5000"


# Initialize Sentiment Analyzer
analyzer = SentimentIntensityAnalyzer()

# Your existing functions here (generate_course_outline, get_video_comments, etc.)
# Paste all your functions here

def generate_course_outline(topic, level):
    """
    Generate a detailed course outline using Groq API
    """
    try:
        prompt = f"""
        You are an expert course builder. Generate a highly detailed, step-by-step learning path for {topic}.
        The user is at {level} level.

        Each major section should contain highly specific subtopics that are YouTube-searchable.
        Ensure the outline is presented in a sequential and progressive learning manner.

        Format the output like this:

        Section 1: Main Topic
          - Subtopic 1 (specific and YouTube-searchable)
          - Subtopic 2 (specific and YouTube-searchable)

        Avoid general titles and focus on concrete, actionable subtopics. Limit to 10 major sections.
        """

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "You are a precise and detailed course creator assistant."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1500,
        }

        response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Error generating course outline: {e}")
        return f"Error: {str(e)}"

def generate_summary(transcript_text):
    """
    Generate a summary of the transcript using Groq API
    """
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": "You are an AI assistant that summarizes an educational YouTube video transcript. Provide a summary using the transcript which can be used by the user for revision such that it goes over all the important concepts."},
                {"role": "user", "content": f"Summarize the following transcript: {transcript_text}"}
            ],
            "max_tokens": 1024,
        }

        response = requests.post(GROQ_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return "Summary not available."

def get_video_comments(video_id):
    """
    Fetch top 30 comments for a given video ID
    """
    try:
        comments = []
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 30,
            "key": YOUTUBE_API_KEY
        }
        response = requests.get(YOUTUBE_COMMENTS_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if "items" in data:
            for item in data["items"]:
                comment_text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                if "http" not in comment_text:  # Exclude comments with links
                    comments.append(comment_text)
        return comments
    except requests.exceptions.HTTPError as e:
        if response.status_code == 403:
            logger.warning(f"Comments disabled or forbidden for video {video_id}")
            return []  # Return empty list instead of failing
        else:
            logger.error(f"HTTP error fetching comments for video {video_id}: {e}")
            return []
    except Exception as e:
        logger.error(f"Error fetching comments for video {video_id}: {e}")
        return []

def get_video_captions(video_id):
    """
    Fetch captions (transcript) for a given video ID
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcripts([video_id])
        if not transcript_list:
            return ""
        transcript = transcript_list[video_id]
        captions_text = ' '.join([item['text'] for item in transcript])
        return captions_text.strip()
    except Exception as e:
        logger.error(f"Error fetching captions for video {video_id}: {e}")
        return ""

def get_sentiment_score(comments):
    """
    Analyze sentiment of comments using VADER
    """
    if not comments:
        return 50  # Neutral score if no comments are found
    
    total_score = 0
    for comment in comments:
        sentiment = analyzer.polarity_scores(comment)
        compound_score = sentiment["compound"]
        
        # Strict scoring conversion
        if compound_score > 0.6:
            scaled_score = 80 + (compound_score * 20)  # Strongly positive
        elif compound_score > 0.2:
            scaled_score = 50 + (compound_score * 30)  # Mildly positive
        elif compound_score < -0.6:
            scaled_score = 10 + (compound_score * 20)  # Strongly negative
        elif compound_score < -0.2:
            scaled_score = 30 + (compound_score * 30)  # Mildly negative
        else:
            scaled_score = 40 + (compound_score * 20)  # Neutral

        total_score += scaled_score
    
    return round(total_score / len(comments), 2)  # Average score

def get_youtube_videos(search_query):
    """
    Search YouTube for videos related to a specific query
    Optimized to reduce latency by limiting comment fetch and parallelizing requests.
    """
    try:
        import concurrent.futures

        # Define search request parameters
        search_params = {
            "part": "snippet",
            "q": search_query,
            "type": "video",
            "maxResults": 20,  # Reduced max results for performance
            "key": YOUTUBE_API_KEY
        }

        # Make the search API request
        response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
        if response.status_code == 403:
            logger.error(f"403 Forbidden error from YouTube API for query: {search_query}. Please check your API key and quota limits.")
            return []
        response.raise_for_status()
        search_data = response.json()

        video_data = []
        if "items" in search_data:
            video_ids = [item["id"]["videoId"] for item in search_data["items"]]

            # Fetch video details including duration in a single batch request
            details_params = {
                "part": ["snippet", "contentDetails", "statistics"],
                "id": ",".join(video_ids),
                "key": YOUTUBE_API_KEY
            }
            details_response = requests.get(YOUTUBE_VIDEO_STATS_URL, params=details_params)
            if details_response.status_code == 403:
                logger.error(f"403 Forbidden error from YouTube API when fetching video details for query: {search_query}. Please check your API key and quota limits.")
                return []
            details_response.raise_for_status()
            details_data = details_response.json()

            def process_video(item):
                try:
                    video_id = item["id"]
                    video_title = item["snippet"]["title"]
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    thumbnail_url = item["snippet"]["thumbnails"]["high"]["url"]

                    duration = isodate.parse_duration(item["contentDetails"]["duration"])
                    duration_minutes = duration.total_seconds() / 60

                    if not (1 <= duration_minutes <= 30):
                        return None

                    # Fetch and analyze comments (limit to 10 for speed)
                    comments = get_video_comments(video_id)[:10]
                    sentiment_score = get_sentiment_score(comments)

                    return {
                        "id": video_id,
                        "Title": video_title,
                        "URL": video_url,
                        "Thumbnail": thumbnail_url,
                        "Duration (minutes)": round(duration_minutes, 2),
                        "Views": item["statistics"].get("viewCount", "N/A"),
                        "Likes": item["statistics"].get("likeCount", "N/A"),
                        "Sentiment Score": sentiment_score
                    }
                except Exception as e:
                    logger.error(f"Error processing video {item.get('id', 'unknown')}: {e}")
                    return None

            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = list(executor.map(process_video, details_data.get("items", [])))

            video_data = [res for res in results if res is not None]

        return video_data
    except Exception as e:
        logger.error(f"Error fetching YouTube videos: {e}")
        return []

def recommend_best_video(df):
    """
    Recommend the best video based on multiple criteria
    """
    try:
        # Convert Views and Likes to numeric, replacing any non-numeric values with 0
        df['Likes'] = pd.to_numeric(df['Likes'], errors='coerce').fillna(0)
        df['Views'] = pd.to_numeric(df['Views'], errors='coerce').fillna(0)
        
        # Calculate likes-to-views ratio (with safety check to prevent division by zero)
        df['likes_to_views_ratio'] = df['Likes'] / (df['Views'] + 1)
        
        # Normalize each metric
        df['likes_norm'] = (df['Likes'] - df['Likes'].min()) / (df['Likes'].max() - df['Likes'].min() + 1e-10)
        df['views_norm'] = (df['Views'] - df['Views'].min()) / (df['Views'].max() - df['Views'].min() + 1e-10)
        df['likes_to_views_ratio_norm'] = (df['likes_to_views_ratio'] - df['likes_to_views_ratio'].min()) / (df['likes_to_views_ratio'].max() - df['likes_to_views_ratio'].min() + 1e-10)
        df['sentiment_norm'] = (df['Sentiment Score'] - df['Sentiment Score'].min()) / (df['Sentiment Score'].max() - df['Sentiment Score'].min() + 1e-10)
        
        # Define weights as specified
        weights = {
            'likes': 0.15,            # 15% weight to likes
            'views': 0.15,            # 15% weight to views
            'likes_to_views_ratio': 0.3,  # 30% weight to likes-to-views ratio
            'sentiment': 0.4          # 40% weight to sentiment score
        }
        
        # Calculate composite recommendation score
        df['recommendation_score'] = (
            (weights['likes'] * df['likes_norm']) + 
            (weights['views'] * df['views_norm']) + 
            (weights['likes_to_views_ratio'] * df['likes_to_views_ratio_norm']) + 
            (weights['sentiment'] * df['sentiment_norm'])
        )
        
        # Find the top recommended video
        best_video = df.loc[df['recommendation_score'].idxmax()]
        return best_video
    except Exception as e:
        logger.error(f"Error recommending best video: {e}")
        return None

def create_learning_path(topic, level):
    """
    Main function to create a complete learning path with course outline and video recommendations
    """
    try:
        # Generate course outline
        course_outline = generate_course_outline(topic, level)
        if "Error" in course_outline:
            return {}

        # Parse course outline into subtopics
        lines = course_outline.split('\n')
        sections = [line.strip() for line in lines if line.strip() and ':' in line][:5]  # Limit to 5 sections for testing to avoid quota exhaustion

        # Recommended learning videos for each section
        section_recommendations = {}
        total_sections = len(sections)
        for i, section in enumerate(sections, 1):
            search_query = section.split(':')[1].strip()
            logger.info(f"Processing section {i}/{total_sections}: {search_query}")
            print(f"🔍 Processing section {i}/{total_sections}: {search_query}")

            # Get YouTube videos
            video_data = get_youtube_videos(search_query)
            if video_data:
                print(f"✅ Found {len(video_data)} videos for {search_query}")
                # Convert to DataFrame
                df = pd.DataFrame(video_data)

                # Recommend best video
                recommended_video = recommend_best_video(df)
                if recommended_video is not None:
                    section_recommendations[section] = recommended_video
                    print(f"🎯 Selected best video: {recommended_video['Title'][:50]}...")
                else:
                    print(f"❌ No best video found for {search_query}")
            else:
                logger.warning(f"No suitable videos found for {search_query}")
                print(f"❌ No videos found for {search_query}")

        return section_recommendations
    except Exception as e:
        logger.error(f"Error creating learning path: {e}")
        return {}

def display_recommendations(topic, level):
    """
    Display recommendations in a Gradio-friendly format with the improved color scheme
    """
    try:
        recommendations = create_learning_path(topic, level)
        if not recommendations:
            return "<p style='color: #496580;'>No recommendations found. Please try a different topic or check the logs for errors.</p>"
        
        # Create a list of cards for each recommendation
        cards = []
        for section, video in recommendations.items():
            # Fetch captions for the video
            captions = get_video_captions(video['id'])
            # Generate summary from captions
            # summary = generate_summary(captions) if captions else ""
            # if summary == "Summary not available." or summary.strip() == "":
            #     summary_html = ""
            # else:
            #     summary_html = f'<div style="background-color: #E8F0FE; padding: 10px; border-radius: 8px; margin-top: 10px; max-height: 150px; overflow-y: auto;">' \
            #                    f'<p style="color: #496580; margin: 0; white-space: pre-wrap;"><b>Summary:</b> {summary}</p></div>'
            card = f"""
            <div style="border: 1px solid #BADDFF; border-radius: 15px; padding: 20px; margin: 15px; width: 320px; display: inline-block; box-shadow: 0 6px 12px rgba(73, 101, 128, 0.15); transition: transform 0.3s; background-color: #FFFFFF;">
                <img src="{video['Thumbnail']}" alt="Thumbnail" style="width: 100%; border-radius: 10px;">
                <h3 style="margin: 15px 0; color: #496580;">{section}</h3>
                <p style="color: #496580;"><b>Title:</b> {video['Title']}</p>
                <p style="color: #496580;"><b>Duration:</b> {video['Duration (minutes)']} minutes</p>
                <p style="color: #496580;"><b>Views:</b> {video['Views']}</p>
                <p style="color: #496580;"><b>Likes:</b> {video['Likes']}</p>
                <div style="background-color: #F0F4F8; padding: 10px; border-radius: 8px; margin-top: 10px;">
                    <p style="color: #496580; margin: 0;"><b>Sentiment Score:</b> {video['Sentiment Score']}</p>
                </div>
                
                <a href="{FLASK_URL}/video/{video['id']}" target="_blank" style="display: block; text-align: center; background: var(--gradient); color: #496580; padding: 12px; border-radius: 8px; text-decoration: none; margin-top: 15px; font-weight: bold;">Watch in Player</a>
            </div>
            """
            cards.append(card)
        
        # Combine all cards into a horizontally scrollable container
        html_output = f"""
        <div style="white-space: nowrap; overflow-x: auto; padding: 15px; scrollbar-width: thin; scrollbar-color: #BADDFF #FFFFFF;">
            {"".join(cards)}
        </div>
        <style>
        ::-webkit-scrollbar {{
          height: 8px;
        }}
        ::-webkit-scrollbar-track {{
          background: #FFFFFF;
        }}
        ::-webkit-scrollbar-thumb {{
          background-color: #BADDFF;
          border-radius: 10px;
        }}
        </style>
        """
        return html_output
    except Exception as e:
        logger.error(f"Error displaying recommendations: {e}")
        return f"<p style='color: #496580;'>An error occurred: {str(e)}</p>"

# Custom CSS for Gradio Interface
custom_css = """
:root {
  --primary-color: #496580;
  --accent-color: #FFDBBB;
  --secondary-color: #BADDFF;
  --tertiary-color: #BAFFF5;
  --bg-color: #FFFFFF;
  --text-color: #496580;
  --gradient: linear-gradient(135deg, #FFDBBB 0%, #BADDFF 50%, #BAFFF5 100%);
}

body {
  font-family: 'Space Grotesk', sans-serif;
  color: var(--text-color);
  background-color: var(--bg-color);
}

.gradio-container {
  max-width: 95% !important;
}

.gr-button {
  background: var(--gradient) !important;
  color: var(--primary-color) !important;
  border: none !important;
  font-weight: bold !important;
}

.gr-input, .gr-dropdown {
  border-color: var(--secondary-color) !important;
  color: var(--primary-color) !important;
}

.gr-form {
  border-radius: 15px !important;
  box-shadow: 0 8px 16px rgba(73, 101, 128, 0.1) !important;
}

.gr-padded {
  padding: 20px !important;
}

h1, h2, h3 {
  color: var(--primary-color) !important;
}

.footer {
  margin-top: 30px;
  text-align: center;
  color: var(--primary-color);
  font-size: 0.9em;
}

.banner {
  background: var(--gradient);
  padding: 20px;
  border-radius: 15px;
  margin-bottom: 20px;
  color: var(--primary-color);
  font-weight: bold;
  text-align: center;
}

.progress-bar {
  height: 8px;
  background: var(--gradient);
  border-radius: 4px;
  margin: 15px 0;
}
"""

# Gradio Interface with improved UI
with gr.Blocks(css=custom_css) as demo:
    gr.HTML("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap" rel="stylesheet">

    <div class="banner">
        <h1 style="margin: 0; font-size: 2.5em;">Student4Students</h1>
        <p style="margin: 10px 0 0 0; font-size: 1.2em;">Your personalized learning journey starts here</p>
    </div>
    """)
    
    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("""
            ### Find the best educational content for your learning journey
            
            > *"The best way to predict the future is to create it."* - Peter Drucker
            
            Student4Students analyzes thousands of videos to find the most helpful content for your specific learning goals, using sentiment analysis and engagement metrics to ensure quality.
            """)
        
        with gr.Column(scale=1):
            gr.HTML("""
            <div style="background-color: #F0F4F8; padding: 15px; border-radius: 15px; border-left: 5px solid #496580;">
                <h4 style="margin-top: 0;">How it works:</h4>
                <ol style="padding-left: 20px; margin-bottom: 0;">
                    <li>Enter your topic of interest</li>
                    <li>Select your current expertise level</li>
                    <li>Generate your personalized learning path</li>
                    <li>Follow the recommended videos in sequence</li>
                </ol>
            </div>
            """)
    
    with gr.Row(equal_height=True):
        with gr.Column():
            topic = gr.Textbox(
                label="What would you like to learn?",
                placeholder="e.g., Machine Learning, Piano, Digital Marketing",
                scale=3
            )
        with gr.Column():
            level = gr.Dropdown(
                label="Your expertise level",
                choices=["Beginner", "Intermediate", "Advanced"],
                value="Beginner",
                scale=1
            )
    
    with gr.Row():
        btn = gr.Button("Generate My Learning Path", scale=1)
    
    with gr.Row():
        gr.HTML("""<div class="progress-bar"></div>""")
    
    output = gr.HTML(label="Recommended Videos")
    
    btn.click(fn=display_recommendations, inputs=[topic, level], outputs=output)
    
    gr.HTML("""
    <div class="footer">
        <p>Built with ❤️ for learners everywhere | © 2025 Student4Students</p>
    </div>
    """)

# Launch the app
if __name__ == "__main__":
    import os
    port = 7870
    # Check if port is available, if not, increment port number until free port found
    import socket
    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    while is_port_in_use(port):
        port += 1

    print(f"Starting Gradio app on port {port}")
    demo.launch(server_name="127.0.0.1", server_port=port, share=True, allowed_paths=["/"])
