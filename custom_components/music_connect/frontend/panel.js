class MusicConnectPanel extends HTMLElement {
  set hass(hass) { this._hass = hass; }
  async apiGet(path) { return this._hass.callApi("GET", path); }
  async apiPost(path, body) { return this._hass.callApi("POST", path, body); }

  connectedCallback() {
    this.activeArtist = "";
    this.selectedPlayer = "";
    this.render();
    this.loadPlayers();
  }

  render() {
    this.innerHTML = `<style>
      .layout{display:grid;grid-template-columns:2fr 1fr;gap:16px;padding:16px}.controls{display:flex;gap:8px;align-items:end;flex-wrap:wrap}
      .graph-wrap{border:1px solid var(--divider-color);border-radius:12px;padding:8px}svg{width:100%;height:460px;background:var(--card-background-color)}
      .side{display:flex;flex-direction:column;gap:12px}.cards{display:grid;grid-template-columns:1fr;gap:8px;max-height:520px;overflow:auto}
      .card{position:relative;display:flex;gap:10px;padding:8px;border:1px solid var(--divider-color);border-radius:10px;cursor:pointer}
      .art{width:56px;height:56px;border-radius:6px;object-fit:cover;background:#333}.play{position:absolute;left:40px;top:40px;border:none;border-radius:50%;width:24px;height:24px;cursor:pointer}
      .bottom{grid-column:1/-1;border-top:1px solid var(--divider-color);padding-top:8px}
    </style>
    <div class="layout">
      <div>
        <h2>Music Neighbourhood</h2>
        <div class="controls"><label>Player <select id="player-select"></select></label><label>Artist <input id="artist-search"/></label><button id="search-button">Explore</button></div>
        <div id="error" style="color:var(--error-color)"></div>
        <div class="graph-wrap"><svg id="graph"></svg></div>
      </div>
      <div class="side">
        <h3>Popular Albums</h3><div id="albums" class="cards"></div>
        <h3>Popular Tracks</h3><div id="tracks" class="cards"></div>
      </div>
      <div class="bottom">Selected player is only used when pressing play.</div>
    </div>`;
    this.querySelector("#search-button").addEventListener("click", () => this.searchArtist());
    this.querySelector("#player-select").addEventListener("change", (e) => { this.selectedPlayer = e.target.value; });
  }

  async loadPlayers() {
    const select = this.querySelector("#player-select");
    const data = await this.apiGet("music_connect/players");
    select.innerHTML = "";
    for (const p of data.players || []) {
      const o = document.createElement("option"); o.value = p.player_id || p.id || ""; o.textContent = p.display_name || p.name || o.value; select.appendChild(o);
    }
    this.selectedPlayer = select.value;
  }

  async searchArtist() {
    const query = this.querySelector("#artist-search").value.trim();
    if (!query) return;
    this.activeArtist = query;
    await this.loadGraph();
    await this.loadMedia();
  }

  async loadGraph() {
    const data = await this.apiGet(`music_connect/lastfm/similar?artist=${encodeURIComponent(this.activeArtist)}&limit=20`);
    this.renderGraph(this.activeArtist, data.similar || []);
  }

  async loadMedia() {
    const data = await this.apiGet(`music_connect/artist_media?artist=${encodeURIComponent(this.activeArtist)}`);
    this.renderCards("albums", data.albums || [], "album");
    this.renderCards("tracks", data.tracks || [], "track");
  }

  renderCards(id, items, type) {
    const wrap = this.querySelector(`#${id}`); wrap.innerHTML = "";
    for (const item of items) {
      const card = document.createElement("div"); card.className = "card";
      card.addEventListener("click", () => { const name = item.artists?.[0]?.name; if (name) { this.activeArtist = name; this.querySelector("#artist-search").value = name; this.loadGraph(); this.loadMedia(); } });
      const img = item.metadata?.images?.[0]?.path || "";
      card.innerHTML = `<img class='art' src='${img}'/><div><div>${item.name || "Unknown"}</div><small>${item.artists?.map(a=>a.name).join(", ") || ""}</small></div>`;
      const play = document.createElement("button"); play.className = "play"; play.textContent = "▶";
      play.addEventListener("click", async (e) => { e.stopPropagation(); await this.playItem(item.uri); });
      card.appendChild(play); wrap.appendChild(card);
    }
  }

  async playItem(uri) {
    if (!this.selectedPlayer) return;
    await this.apiPost("music_connect/play", { player_id: this.selectedPlayer, media_uri: uri });
  }

  renderGraph(centerArtist, similarArtists) {
    const svg = this.querySelector("#graph"); svg.innerHTML = ""; const width = svg.clientWidth || 900; const height = svg.clientHeight || 520; const cx = width/2; const cy = height/2; const ns = "http://www.w3.org/2000/svg";
    const drawNode = (name,x,y,r,fill)=>{ const c=document.createElementNS(ns,"circle"); c.setAttribute("cx",x); c.setAttribute("cy",y); c.setAttribute("r",r); c.setAttribute("fill",fill); c.style.cursor="pointer"; c.onclick=async()=>{this.activeArtist=name; this.querySelector("#artist-search").value=name; await this.loadGraph(); await this.loadMedia();}; svg.appendChild(c); const t=document.createElementNS(ns,"text"); t.setAttribute("x",x); t.setAttribute("y",y+4); t.setAttribute("fill","var(--primary-text-color)"); t.setAttribute("text-anchor","middle"); t.textContent=name.slice(0,18); svg.appendChild(t); };
    drawNode(centerArtist,cx,cy,42,"#5e9cff"); const radius=Math.min(width,height)*0.35;
    similarArtists.slice(0,20).forEach((artist,i,arr)=>{const angle=(2*Math.PI*i)/arr.length; const match=Number.parseFloat(artist.match||"0")||0; const distance=radius+(1-match)*90; const x=cx+Math.cos(angle)*distance; const y=cy+Math.sin(angle)*distance; const line=document.createElementNS(ns,"line"); line.setAttribute("x1",cx); line.setAttribute("y1",cy); line.setAttribute("x2",x); line.setAttribute("y2",y); line.setAttribute("stroke","#7a7a7a"); line.setAttribute("stroke-width",`${1+match*3}`); svg.appendChild(line); drawNode(artist.name||"Unknown",x,y,20+match*12,`hsl(${200-Math.floor(match*120)} 75% 55%)`);});
  }
}
customElements.define("music-connect-panel", MusicConnectPanel);
