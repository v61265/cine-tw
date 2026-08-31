const state = {
  cinemas: {},
  films: {},
  screenings: [],
  selectedDate: null,
  selectedLanguages: new Set(),
  selectedCinemas: new Set(),
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

function buildDateTabs() {
  const dates = [...new Set(state.screenings.map((s) => localDateKey(s.datetime_start)))].sort();
  const todayKey = taipeiTodayKey();
  state.selectedDate = dates.includes(todayKey) ? todayKey : dates[0];

  const container = document.getElementById("date-tabs");
  container.innerHTML = "";
  for (const dateKey of dates) {
    const d = new Date(dateKey + "T00:00:00");
    const label = `${d.getMonth() + 1}/${d.getDate()}(${"日一二三四五六"[d.getDay()]})`;
    const btn = document.createElement("button");
    btn.className = "date-tab" + (dateKey === state.selectedDate ? " active" : "");
    btn.textContent = label;
    btn.onclick = () => {
      state.selectedDate = dateKey;
      container.querySelectorAll(".date-tab").forEach((el) => el.classList.remove("active"));
      btn.classList.add("active");
      render();
    };
    container.appendChild(btn);
  }
}

function buildLanguageFilters() {
  const langs = [...new Set(state.screenings.map((s) => s.language || "未知"))].sort();
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

function buildCinemaFilters() {
  const chainIds = Object.entries(state.cinemas)
    .filter(([, c]) => c.chain)
    .map(([id]) => id);
  const indieIds = Object.entries(state.cinemas)
    .filter(([, c]) => !c.chain)
    .map(([id]) => id);

  state.selectedCinemas = new Set(Object.keys(state.cinemas));

  const renderGroup = (containerId, ids) => {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    for (const id of ids.sort((a, b) => state.cinemas[a].name.localeCompare(state.cinemas[b].name, "zh-Hant"))) {
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = true;
      checkbox.onchange = () => {
        checkbox.checked ? state.selectedCinemas.add(id) : state.selectedCinemas.delete(id);
        render();
      };
      label.append(checkbox, document.createTextNode(state.cinemas[id].name));
      container.appendChild(label);
    }
  };
  renderGroup("chain-cinema-filters", chainIds);
  renderGroup("indie-cinema-filters", indieIds);
}

function render() {
  const filtered = state.screenings.filter(
    (s) =>
      localDateKey(s.datetime_start) === state.selectedDate &&
      state.selectedLanguages.has(s.language || "未知") &&
      state.selectedCinemas.has(s.cinema_id)
  );

  const byFilm = new Map();
  for (const s of filtered) {
    if (!byFilm.has(s.film_id)) byFilm.set(s.film_id, []);
    byFilm.get(s.film_id).push(s);
  }

  const results = document.getElementById("results");
  results.innerHTML = "";

  if (byFilm.size === 0) {
    results.innerHTML = '<p class="empty">這天沒有符合篩選條件的場次</p>';
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

    const card = document.createElement("div");
    card.className = "film-card";

    const title = document.createElement("h3");
    title.className = "film-title";
    title.textContent = film.normalized_title;
    card.appendChild(title);

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
  buildDateTabs();
  buildLanguageFilters();
  buildCinemaFilters();
  render();
});
