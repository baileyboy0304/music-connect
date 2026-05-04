class MusicConnectPanel extends HTMLElement {
  connectedCallback() {
    this.render();
    this.loadPlayers();
  }

  render() {
    this.innerHTML = `
      <div style="padding:16px;">
        <h1>Music Neighbourhood</h1>
        <label for="player-select">Player:</label>
        <select id="player-select">
          <option>Loading players...</option>
        </select>

        <div style="margin-top:16px;">
          <label for="artist-search">Artist search:</label>
          <input id="artist-search" type="text" placeholder="Type an artist" />
          <button id="search-button">Search</button>
        </div>

        <pre id="search-results" style="margin-top:16px;white-space:pre-wrap;"></pre>
      </div>
    `;

    this.querySelector("#search-button").addEventListener("click", () => {
      this.searchArtist();
    });
  }

  async loadPlayers() {
    const select = this.querySelector("#player-select");
    try {
      const response = await fetch("/api/music_connect/players", {
        credentials: "same-origin",
      });
      const data = await response.json();
      select.innerHTML = "";
      for (const player of data.players || []) {
        const option = document.createElement("option");
        option.value = player.player_id || player.id || "unknown";
        option.textContent = player.display_name || player.name || option.value;
        select.appendChild(option);
      }
      if (!select.children.length) {
        select.innerHTML = "<option>No players found</option>";
      }
    } catch (err) {
      select.innerHTML = "<option>Failed to load players</option>";
    }
  }

  async searchArtist() {
    const query = this.querySelector("#artist-search").value.trim();
    const output = this.querySelector("#search-results");

    if (!query) {
      output.textContent = "Enter an artist to search.";
      return;
    }

    try {
      const response = await fetch(`/api/music_connect/search?q=${encodeURIComponent(query)}`, {
        credentials: "same-origin",
      });
      const data = await response.json();
      output.textContent = JSON.stringify(data.results, null, 2);
    } catch (err) {
      output.textContent = "Search failed.";
    }
  }
}

customElements.define("music-connect-panel", MusicConnectPanel);
