document.addEventListener("DOMContentLoaded", () => {
  const searchBtn = document.getElementById("search-btn");
  const queryInput = document.getElementById("query");
  const videoTitle = document.getElementById("video-title");
  const videoContainer = document.getElementById("video-container");
  const transcriptSection = document.getElementById("transcript");
  const transcriptControls = document.getElementById("transcript-controls");
  const languageSelector = document.getElementById("language-selector");

  if (searchBtn) {
    searchBtn.addEventListener("click", async () => {
      const query = queryInput.value.trim();
      if (!query) {
        alert("Please enter a search query.");
        return;
      }

      videoContainer.innerHTML = "<p class='loading'>🔍 Searching...</p>";
      transcriptSection.innerHTML = "";
      transcriptControls.style.display = "none";
      videoTitle.textContent = "Loading...";

      try {
        const response = await fetch("/search", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: `query=${encodeURIComponent(query)}`,
        });
        const data = await response.json();

        if (data.error) {
          videoContainer.innerHTML = `<p class='error'>❌ ${data.error}</p>`;
          videoTitle.textContent = "Error";
        } else {
          // Redirect to Flask app video page with video ID
          window.location.href = `/video/${data.id}`;
        }
      } catch (error) {
        videoContainer.innerHTML = "<p class='error'>❌ Failed to fetch videos. Try again.</p>";
        videoTitle.textContent = "Error";
      }
    });
  }
});
