class MusicConnectPanel extends HTMLElement {
  static get properties() { return { hass: {}, narrow: {}, route: {}, panel: {} }; }
  set hass(hass) { this._hass = hass; }
  async apiGet(path) { return this._hass.callApi("GET", path); }
  async apiPost(path, body) { return this._hass.callApi("POST", path, body); }

  connectedCallback() {
    this.activeArtist = ""; this.selectedPlayer = ""; this.expandedAlbums = new Map();
    this.render(); this.loadPlayers();
  }

  toggleMenu() { this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true })); }

  render() {
    this.innerHTML = `<style>
      .layout{display:grid;grid-template-columns:2fr 1fr;gap:16px;padding:16px}.controls{display:flex;gap:8px;align-items:end;flex-wrap:wrap}
      .top{display:flex;align-items:center;gap:8px}.menu{display:none}
      .graph-wrap{border:1px solid var(--divider-color);border-radius:12px;padding:8px}svg{width:100%;height:460px;background:linear-gradient(180deg, color-mix(in srgb, var(--card-background-color) 92%, #dce2e7), var(--card-background-color))}
      .side{display:flex;flex-direction:column;gap:12px}.cards{display:grid;grid-template-columns:1fr;gap:8px;max-height:520px;overflow:auto}
      .card{position:relative;display:flex;gap:10px;padding:8px;border:1px solid var(--divider-color);border-radius:10px;cursor:pointer}
      .art{width:56px;height:56px;border-radius:6px;object-fit:cover;background:#333}.play{position:absolute;left:40px;top:40px;border:none;border-radius:50%;width:24px;height:24px;cursor:pointer}
      .album-tracks{margin-left:66px;display:grid;gap:6px}.album-track{display:flex;justify-content:space-between;border:1px dashed var(--divider-color);padding:6px;border-radius:8px}
      .bottom{grid-column:1/-1;border-top:1px solid var(--divider-color);padding-top:8px}
      @media (max-width: 870px){.layout{grid-template-columns:1fr}.menu{display:inline-block}}
    </style>
    <div class="layout">
      <div>
        <div class="top"><button id="menu-button" class="menu">☰</button><h2>Music Neighbourhood</h2></div>
        <div class="controls"><label>Player <select id="player-select"></select></label><label>Artist <input id="artist-search"/></label><button id="search-button">Explore</button></div>
        <div id="error" style="color:var(--error-color)"></div>
        <div class="graph-wrap"><svg id="graph"></svg></div>
      </div>
      <div class="side"><h3>Popular Albums</h3><div id="albums" class="cards"></div><h3>Popular Tracks</h3><div id="tracks" class="cards"></div></div>
      <div class="bottom">Selected player is only used when pressing play.</div>
    </div>`;
    this.querySelector("#menu-button").addEventListener("click", () => this.toggleMenu());
    this.querySelector("#search-button").addEventListener("click", () => this.searchArtist());
    this.querySelector("#player-select").addEventListener("change", async (e) => { this.selectedPlayer = e.target.value; await this.apiPost("music_connect/preferences", { default_player: this.selectedPlayer }); localStorage.setItem("music_connect_default_player", this.selectedPlayer); });
  }

  async loadPlayers() {
    const select = this.querySelector("#player-select");
    const [playersData, prefData] = await Promise.all([this.apiGet("music_connect/players"), this.apiGet("music_connect/preferences")]);
    select.innerHTML = "";
    (playersData.players || []).forEach((p) => { const o = document.createElement("option"); o.value = p.player_id || p.id || ""; o.textContent = p.display_name || p.name || o.value; select.appendChild(o); });
    const local = localStorage.getItem("music_connect_default_player");
    const preferred = prefData.default_player || local;
    if (preferred && [...select.options].some((o) => o.value === preferred)) select.value = preferred;
    this.selectedPlayer = select.value;
    await this.seedFromCurrentPlayer(playersData.players || []);
  }
  async seedFromCurrentPlayer(players) {
    if (this.activeArtist || !this.selectedPlayer) return;
    const player = players.find((p) => (p.player_id || p.id) === this.selectedPlayer);
    const artist = player?.current_media?.artist || player?.current_item?.artists?.[0]?.name || player?.elapsed_time_last_updated_item?.artists?.[0]?.name;
    if (artist) {
      this.activeArtist = artist;
      this.querySelector("#artist-search").value = artist;
      await this.loadGraph();
      await this.loadMedia();
    }
  }
  async searchArtist() { const query=this.querySelector("#artist-search").value.trim(); if(!query)return; this.activeArtist=query; await this.loadGraph(); await this.loadMedia(); }
  async loadGraph() { const data=await this.apiGet(`music_connect/lastfm/similar?artist=${encodeURIComponent(this.activeArtist)}&limit=20`); this.renderGraph(this.activeArtist,data.similar||[]); }
  async loadMedia() { const data=await this.apiGet(`music_connect/artist_media?artist=${encodeURIComponent(this.activeArtist)}`); this.renderCards("albums",data.albums||[],"album"); this.renderCards("tracks",data.tracks||[],"track"); }

  async toggleAlbumDetails(container, albumItem) {
    const key = albumItem.uri || `${this.activeArtist}::${albumItem.name}`;
    if (this.expandedAlbums.get(key)) { this.expandedAlbums.delete(key); this.renderCards("albums", this._albumsCache || [], "album"); return; }
    const data = await this.apiGet(`music_connect/album_tracks?album_uri=${encodeURIComponent(albumItem.uri || "")}`);
    this.expandedAlbums.set(key, data.tracks || []);
    this.renderCards("albums", this._albumsCache || [], "album");
  }

  renderCards(id, items, type) {
    if (id === "albums") this._albumsCache = items;
    const wrap=this.querySelector(`#${id}`); wrap.innerHTML="";
    for (const item of items) {
      const card=document.createElement("div"); card.className="card";
      card.addEventListener("click", async ()=>{
        if (type === "album") return this.toggleAlbumDetails(wrap, item);
        const name=item.artists?.[0]?.name; if(name){this.activeArtist=name; this.querySelector("#artist-search").value=name; await this.loadGraph(); await this.loadMedia();}
      });
      const img=item.metadata?.images?.[0]?.path||"";
      card.innerHTML=`<img class='art' src='${img}'/><div><div>${item.name||"Unknown"}</div><small>${item.artists?.map(a=>a.name).join(", ")||""}</small></div>`;
      const play=document.createElement("button"); play.className="play"; play.textContent="▶";
      play.addEventListener("click", async(e)=>{e.stopPropagation(); await this.playItem(item.uri);});
      card.appendChild(play); wrap.appendChild(card);

      if (type === "album") {
        const key = item.uri || `${this.activeArtist}::${item.name}`;
        const tracks = this.expandedAlbums.get(key);
        if (tracks) {
          const details = document.createElement("div"); details.className = "album-tracks";
          tracks.forEach((t) => {
            const row = document.createElement("div"); row.className = "album-track";
            row.innerHTML = `<span>${t.track_number || ""} ${t.name || "Track"}</span>`;
            const b = document.createElement("button"); b.textContent = "▶";
            b.addEventListener("click", async (e) => { e.stopPropagation(); await this.playItem(t.uri); });
            row.appendChild(b); details.appendChild(row);
          });
          wrap.appendChild(details);
        }
      }
    }
  }

  async playItem(uri){ if(!this.selectedPlayer) return; await this.apiPost("music_connect/play",{player_id:this.selectedPlayer,media_uri:uri}); }

  renderGraph(centerArtist, similarArtists) {
    const svg=this.querySelector("#graph"); svg.innerHTML="";
    const width=svg.clientWidth||900,height=svg.clientHeight||520,cx=width/2,cy=height/2,ns="http://www.w3.org/2000/svg";
    const wrapText = (name, max) => { const parts = []; let line = ""; for (const w of (name || "").split(" ")) { const n = line ? `${line} ${w}` : w; if (n.length > max && line) { parts.push(line); line = w; } else line = n; } if (line) parts.push(line); return parts.slice(0, 3); };
    const drawNode=(name,x,y,r,fill,isCenter=false)=>{const c=document.createElementNS(ns,"circle"); c.setAttribute("cx",x); c.setAttribute("cy",y); c.setAttribute("r",r); c.setAttribute("fill",fill); c.setAttribute("stroke", isCenter ? "#2c2a70" : "#1d4f59"); c.setAttribute("stroke-width", isCenter ? "3" : "1.5"); c.style.cursor="pointer"; c.onclick=async()=>{this.activeArtist=name; this.querySelector("#artist-search").value=name; await this.loadGraph(); await this.loadMedia();}; svg.appendChild(c); const lines=wrapText(name,isCenter?14:12); lines.forEach((line, idx)=>{const t=document.createElementNS(ns,"text"); t.setAttribute("x",x); t.setAttribute("y",y-((lines.length-1)*8)+idx*16+4); t.setAttribute("fill","#fff"); t.setAttribute("font-size", isCenter ? "18" : "13"); t.setAttribute("font-weight", isCenter ? "700" : "600"); t.setAttribute("text-anchor","middle"); t.textContent=line; svg.appendChild(t);});};
    drawNode(centerArtist,cx,cy,70,"#3c357e",true);
    const radius=Math.min(width,height)*0.38;
    similarArtists.slice(0,20).forEach((artist,i,arr)=>{const angle=(2*Math.PI*i)/arr.length,match=Number.parseFloat(artist.match||"0")||0,distance=radius+(1-match)*110,x=cx+Math.cos(angle)*distance,y=cy+Math.sin(angle)*distance; const line=document.createElementNS(ns,"line"); line.setAttribute("x1",cx); line.setAttribute("y1",cy); line.setAttribute("x2",x); line.setAttribute("y2",y); line.setAttribute("stroke",match>0.5?"#4a8f96":"#8b5a5a"); line.setAttribute("stroke-width",`${1+match*2.5}`); svg.appendChild(line); const nodeColor=match>0.66?"#3f7f80":(match>0.33?"#6d3232":"#4b5357"); drawNode(artist.name||"Unknown",x,y,34,nodeColor,false);});
  }
}
customElements.define("music-connect-panel", MusicConnectPanel);
