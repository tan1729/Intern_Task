# TODO: Fix Video Playback and Auto-Generation on Flask App (Port 5000)

## Completed Tasks
- [x] Add `/summary` route in `app.py` to generate summary for a video ID
- [x] Add `/translate_summary` route in `app.py` for translating summaries
- [x] Update `script.js` to auto-fetch transcript and summary when video page loads
- [x] Add event listeners for summary buttons (generate, translate, download)
- [x] Fix YouTubeTranscriptApi instantiation errors in `app.py`

## Next Steps
- [ ] Test the Flask app by running it and accessing a video page via redirect from Gradio
- [ ] Verify that transcript and summary are auto-generated on load
- [ ] Check if subtitles overlay works with the fetched transcript
- [ ] Ensure translation and download features work correctly
- [ ] Handle any errors or edge cases (e.g., videos without transcripts)

## Notes
- Auto-fetching is enabled on video page load for better UX
- Summary generation uses Groq API
- Translation uses GoogleTranslator
- Download saves summary as .txt file
