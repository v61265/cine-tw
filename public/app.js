const CHAIN_LABELS = { ambassador: "國賓影城" };

const state = {
  cinemas: {},
  films: {},
  screenings: [],
  selectedDate: null,
  selectedLanguages: new Set(),
  selectedCinemas: new Set(),
  selectedCities: new Set(),
  searchQuery: "",
};

async function loadData() {
  const [cinemas, films, screenings, meta] = await Promise.all([
    fetch("data/cinemas.json").then((r) => r.json()),
    fetch("data/films.json").then((r) => r.json()),
    fetch("data/screenings.json").then((r) => r.json()),
    fetch("data/meta.json").then((r) => r.json()),
  ]);
  state.cinemas = cinemas;
  state.films = films;
  state.screenings = screenings;

  const genAt = new Date(meta.generated_at);
  document.getElementById("meta-line").textContent =
    `資料更新於 ${genAt.toLocaleString("zh-TW", { dateStyle: "medium", timeStyle: "short" })}` +
    ` · ${state.screenings.length} 筆場次 · ${Object.keys(state.cinemas).length} 家影院`;
}

function localDateKey(isoString) {
  return isoString.slice(0, 10); // "YYYY-MM-DD", already local wall time
}

function taipeiTodayKey() {
  // Screening times are Taiwan wall-clock dates with no timezone info, so
  // "today" has to be computed in Asia/Taipei too — otherwise a viewer
  // (or this server) between 00:00-08:00 Taipei time gets the UTC date,
  // which is still "yesterday" locally.
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Taipei" }).format(new Date());
}

function taipeiNowKey() {
  // Same reasoning as taipeiTodayKey but down to the second, so it can be
  // string-compared directly against a naive "YYYY-MM-DDTHH:MM:SS"
  // datetime_start (lexicographic order matches chronological order for
  // zero-padded ISO-shaped strings).
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date());
  const get = (type) => parts.find((p) => p.type === type).value;
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}:${get("second")}`;
}

function buildTitleSearch() {
  const input = document.getElementById("title-search");
  input.oninput = () => {
    state.searchQuery = input.value.trim().toLowerCase();
    render();
  };
}

function buildDateTabs() {
  const dates = [...new Set(state.screenings.map((s) => localDateKey(s.datetime_start)))].sort();
  const todayKey = taipeiTodayKey();
  state.selectedDate = dates.includes(todayKey) ? todayKey : dates[0];

  const select = document.getElementById("date-tabs");
  select.innerHTML = "";
  for (const dateKey of dates) {
    const d = new Date(dateKey + "T00:00:00");
    const label = `${d.getMonth() + 1}/${d.getDate()}(${"日一二三四五六"[d.getDay()]})`;
    const option = document.createElement("option");
    option.value = dateKey;
    option.textContent = label;
    if (dateKey === state.selectedDate) option.selected = true;
    select.appendChild(option);
  }
  select.onchange = () => {
    state.selectedDate = select.value;
    render();
  };
}

const OTHER_LANGUAGE = "其他";
const LANGUAGE_ORDER = ["中文版", "英文版", "日文版"]; // OTHER_LANGUAGE always sorts last

function rankIn(list, value) {
  const i = list.indexOf(value);
  return i === -1 ? list.length : i;
}

function buildLanguageFilters() {
  const langs = [...new Set(state.screenings.map((s) => s.language || OTHER_LANGUAGE))].sort(
    (a, b) => rankIn(LANGUAGE_ORDER, a) - rankIn(LANGUAGE_ORDER, b) || a.localeCompare(b, "zh-Hant")
  );
  state.selectedLanguages = new Set(langs);

  const container = document.getElementById("language-filters");
  container.innerHTML = "";
  for (const lang of langs) {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.onchange = () => {
      checkbox.checked ? state.selectedLanguages.add(lang) : state.selectedLanguages.delete(lang);
      render();
    };
    label.append(checkbox, document.createTextNode(lang));
    container.appendChild(label);
  }
}

function cinemaCheckboxLabel(id) {
  const label = document.createElement("label");
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = true;
  checkbox.onchange = () => {
    checkbox.checked ? state.selectedCinemas.add(id) : state.selectedCinemas.delete(id);
    render();
  };
  label.append(checkbox, document.createTextNode(state.cinemas[id].name));
  return label;
}

function byZhName(ids) {
  return ids.sort((a, b) => state.cinemas[a].name.localeCompare(state.cinemas[b].name, "zh-Hant"));
}

function buildCinemaFilters() {
  state.selectedCinemas = new Set(Object.keys(state.cinemas));

  const chains = new Map(); // chain key -> [cinema ids]
  const indieIds = [];
  for (const [id, c] of Object.entries(state.cinemas)) {
    if (c.chain) {
      if (!chains.has(c.chain)) chains.set(c.chain, []);
      chains.get(c.chain).push(id);
    } else {
      indieIds.push(id);
    }
  }

  const chainContainer = document.getElementById("chain-cinema-filters");
  chainContainer.innerHTML = "";
  for (const [chainKey, ids] of chains) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `${CHAIN_LABELS[chainKey] ?? chainKey}（${ids.length}）`;
    details.appendChild(summary);
    for (const id of byZhName(ids)) details.appendChild(cinemaCheckboxLabel(id));
    chainContainer.appendChild(details);
  }

  const indieContainer = document.getElementById("indie-cinema-filters");
  indieContainer.innerHTML = "";
  for (const id of byZhName(indieIds)) indieContainer.appendChild(cinemaCheckboxLabel(id));
}

// North to south, 台北市 pinned first per request even though 基隆市 is
// arguably just as far north — everything else follows rough geography.
const CITY_ORDER = [
  "台北市", "基隆市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
  "台中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "台南市",
  "高雄市", "屏東縣", "屏東市", "宜蘭縣", "花蓮縣", "台東縣",
  "澎湖縣", "金門縣", "連江縣",
];

function buildCityFilters() {
  const cities = [...new Set(Object.values(state.cinemas).map((c) => c.city || "未知"))].sort(
    (a, b) => rankIn(CITY_ORDER, a) - rankIn(CITY_ORDER, b) || a.localeCompare(b, "zh-Hant")
  );
  state.selectedCities = new Set(cities);

  const container = document.getElementById("city-filters");
  container.innerHTML = "";
  for (const city of cities) {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.onchange = () => {
      checkbox.checked ? state.selectedCities.add(city) : state.selectedCities.delete(city);
      render();
    };
    label.append(checkbox, document.createTextNode(city));
    container.appendChild(label);
  }
}

function filmMatchesSearch(film, query) {
  const haystacks = [film.normalized_title, film.original_title, ...film.raw_titles];
  return haystacks.some((t) => t && t.toLowerCase().includes(query));
}

function render() {
  const nowKey = taipeiNowKey();
  const filtered = state.screenings.filter(
    (s) =>
      localDateKey(s.datetime_start) === state.selectedDate &&
      s.datetime_start >= nowKey &&
      state.selectedLanguages.has(s.language || OTHER_LANGUAGE) &&
      state.selectedCinemas.has(s.cinema_id) &&
      state.selectedCities.has(state.cinemas[s.cinema_id]?.city || "未知")
  );

  const byFilm = new Map();
  for (const s of filtered) {
    if (state.searchQuery && !filmMatchesSearch(state.films[s.film_id], state.searchQuery)) continue;
    if (!byFilm.has(s.film_id)) byFilm.set(s.film_id, []);
    byFilm.get(s.film_id).push(s);
  }

  const results = document.getElementById("results");
  results.innerHTML = "";

  if (byFilm.size === 0) {
    results.innerHTML =
      '<p class="empty">這天沒有符合篩選條件的場次，可能已經全部開始播放了，換個日期看看？</p>';
    return;
  }

  const filmEntries = [...byFilm.entries()].sort((a, b) => {
    const aMin = Math.min(...a[1].map((s) => s.datetime_start));
    const bMin = Math.min(...b[1].map((s) => s.datetime_start));
    return aMin < bMin ? -1 : aMin > bMin ? 1 : 0;
  });

  for (const [filmId, showtimes] of filmEntries) {
    const film = state.films[filmId];
    showtimes.sort((a, b) => (a.datetime_start < b.datetime_start ? -1 : 1));

    const card = document.createElement("details");
    card.className = "film-card";

    const summary = document.createElement("summary");

    const summaryTop = document.createElement("div");
    summaryTop.className = "summary-top";
    const title = document.createElement("span");
    title.className = "film-title";
    title.textContent = film.normalized_title;
    summaryTop.appendChild(title);
    const count = document.createElement("span");
    count.className = "film-count";
    count.textContent = `${showtimes.length} 場`;
    summaryTop.appendChild(count);
    summary.appendChild(summaryTop);

    const metaBits = [];
    if (film.director) metaBits.push(film.director);
    if (film.year) metaBits.push(String(film.year));

    const filmMeta = document.createElement("p");
    filmMeta.className = "film-meta";
    if (metaBits.length) filmMeta.append(document.createTextNode(metaBits.join(" · ") + " · "));
    const lbLink = document.createElement("a");
    lbLink.className = "letterboxd-link";
    lbLink.href = `https://letterboxd.com/search/${encodeURIComponent(film.original_title || film.normalized_title)}/`;
    lbLink.target = "_blank";
    lbLink.rel = "noopener";
    lbLink.textContent = "Letterboxd ↗";
    filmMeta.appendChild(lbLink);
    summary.appendChild(filmMeta);

    card.appendChild(summary);

    const altTitles = film.raw_titles.filter((t) => t !== film.normalized_title);
    if (altTitles.length) {
      const alt = document.createElement("p");
      alt.className = "film-original-title";
      alt.textContent = altTitles.join(" / ");
      card.appendChild(alt);
    }

    for (const s of showtimes) {
      const row = document.createElement("div");
      row.className = "showtime-row";

      const time = document.createElement("span");
      time.className = "showtime-time";
      time.textContent = s.datetime_start.slice(11, 16);
      row.appendChild(time);

      const cinema = document.createElement("span");
      cinema.className = "showtime-cinema";
      cinema.textContent = state.cinemas[s.cinema_id]?.name ?? s.cinema_id;
      row.appendChild(cinema);

      if (s.language) {
        const tag = document.createElement("span");
        tag.className = "showtime-tag";
        tag.textContent = s.language;
        row.appendChild(tag);
      }

      if (s.booking_url) {
        const link = document.createElement("a");
        link.className = "book-link";
        link.href = s.booking_url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = "訂票";
        row.appendChild(link);
      } else {
        const none = document.createElement("span");
        none.className = "book-none";
        none.textContent = s.booking_platform === "onsite" ? "現場購票" : "洽影院";
        row.appendChild(none);
      }

      card.appendChild(row);
    }

    results.appendChild(card);
  }
}

loadData().then(() => {
  buildTitleSearch();
  buildDateTabs();
  buildLanguageFilters();
  buildCityFilters();
  buildCinemaFilters();
  render();
});
