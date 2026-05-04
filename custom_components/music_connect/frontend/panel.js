class MusicConnectPanel extends HTMLElement {
  connectedCallback() {
    this.activeArtist = "";
    this.render();
    this.loadPlayers();
  }

  render() {
    this.innerHTML = `
      <style>
        .layout { display: grid; grid-template-columns: 1fr; gap: 16px; padding: 16px; }
        .controls { display: flex; gap: 12px; align-items: end; flex-wrap: wrap; }
        .graph-wrap { border: 1px solid var(--divider-color); border-radius: 12px; padding: 8px; }
        svg { width: 100%; height: 520px; background: var(--card-background-color); border-radius: 8px; }
        .bubble { cursor: pointer; }
        .label { fill: var(--primary-text-color); font-size: 12px; text-anchor: middle; pointer-events: none; }
      </style>
      <div class="layout">
        <h1>Music Neighbourhood</h1>
        <div class="controls">
          <label>Player <select id="player-select"><option>Loading players...</option></select></label>
          <label>Artist <input id="artist-search" type="text" placeholder="Type an artist" /></label>
          <button id="search-button">Explore</button>
        </div>
        <div id="error" style="color: var(--error-color);"></div>
        <div class="graph-wrap"><svg id="graph"></svg></div>
      </div>
    `;
    this.querySelector("#search-button").addEventListener("click", () => this.searchArtist());
  }

  async loadPlayers() { /* unchanged behavior */
    const select = this.querySelector("#player-select");
    try {
      const response = await fetch("/api/music_connect/players", { credentials: "same-origin" });
      const data = await response.json();
      select.innerHTML = "";
      for (const player of data.players || []) {
        const option = document.createElement("option");
        option.value = player.player_id || player.id || "unknown";
        option.textContent = player.display_name || player.name || option.value;
        select.appendChild(option);
      }
      if (!select.children.length) select.innerHTML = "<option>No players found</option>";
    } catch (err) {
      select.innerHTML = "<option>Failed to load players</option>";
    }
  }

  async searchArtist() {
    const query = this.querySelector("#artist-search").value.trim();
    if (!query) return;
    this.activeArtist = query;
    await this.loadGraph();
  }

  async loadGraph() {
    const errorEl = this.querySelector("#error");
    errorEl.textContent = "";
    try {
      const res = await fetch(`/api/music_connect/lastfm/similar?artist=${encodeURIComponent(this.activeArtist)}&limit=20`, { credentials: "same-origin" });
      const data = await res.json();
      this.renderGraph(this.activeArtist, data.similar || []);
    } catch (e) {
      errorEl.textContent = "Failed to load Last.fm similar artists.";
    }
  }

  renderGraph(centerArtist, similarArtists) {
    const svg = this.querySelector("#graph");
    svg.innerHTML = "";
    const width = svg.clientWidth || 900;
    const height = svg.clientHeight || 520;
    const cx = width / 2;
    const cy = height / 2;

    const ns = "http://www.w3.org/2000/svg";
    const drawNode = (name, x, y, r, fill) => {
      const c = document.createElementNS(ns, "circle");
      c.setAttribute("cx", x); c.setAttribute("cy", y); c.setAttribute("r", r);
      c.setAttribute("fill", fill); c.setAttribute("class", "bubble");
      c.addEventListener("click", async () => { this.activeArtist = name; this.querySelector("#artist-search").value = name; await this.loadGraph(); });
      svg.appendChild(c);
      const t = document.createElementNS(ns, "text");
      t.setAttribute("x", x); t.setAttribute("y", y + 4); t.setAttribute("class", "label");
      t.textContent = name.length > 18 ? `${name.slice(0, 16)}…` : name;
      svg.appendChild(t);
    };

    drawNode(centerArtist, cx, cy, 42, "#5e9cff");
    const radius = Math.min(width, height) * 0.35;
    similarArtists.slice(0, 20).forEach((artist, i, arr) => {
      const angle = (2 * Math.PI * i) / arr.length;
      const match = Number.parseFloat(artist.match || "0") || 0;
      const distance = radius + (1 - match) * 90;
      const x = cx + Math.cos(angle) * distance;
      const y = cy + Math.sin(angle) * distance;

      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", cx); line.setAttribute("y1", cy); line.setAttribute("x2", x); line.setAttribute("y2", y);
      line.setAttribute("stroke", "#7a7a7a"); line.setAttribute("stroke-width", `${1 + match * 3}`);
      svg.appendChild(line);

      const size = 20 + match * 12;
      const color = `hsl(${200 - Math.floor(match * 120)} 75% 55%)`;
      drawNode(artist.name || "Unknown", x, y, size, color);
    });
  }
}
customElements.define("music-connect-panel", MusicConnectPanel);
