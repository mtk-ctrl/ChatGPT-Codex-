(() => {
  "use strict";
  const calendarData = document.getElementById("calendar-data");
  if (calendarData) {
    const data = JSON.parse(calendarData.textContent);
    const grid = document.getElementById("calendar-grid");
    const month = document.getElementById("calendar-month");
    const previous = document.getElementById("calendar-prev");
    const next = document.getElementById("calendar-next");
    const records = new Map();
    data.records.forEach(record => {
      if (!records.has(record.day)) records.set(record.day, []);
      records.get(record.day).push(record);
    });
    let selected = data.selected;
    const element = (tag, text, className) => {
      const node = document.createElement(tag);
      if (text !== undefined) node.textContent = text;
      if (className) node.className = className;
      return node;
    };
    const details = day => {
      selected = day;
      const [year, number, date] = day.split("-").map(Number);
      document.getElementById("selected-date").textContent = `${year}年${number}月${date}日の情報`;
      const target = document.getElementById("selected-records");
      target.replaceChildren();
      if (day === data.predicted) {
        target.append(element("p", "当サイトの予想日です。", "predicted-day-note"));
      }
      const rows = records.get(day) || [];
      if (!rows.length) target.append(element("p", "この日の情報はありません。", "empty-day"));
      ["global", "banked"].forEach(kind => {
        const posts = rows.filter(row => row.kind === kind);
        if (!posts.length) return;
        const article = element("article", undefined, "day-record");
        article.append(element("h4", kind === "global" ? "リセット" : "リセットチケット"));
        article.append(element("p", `${posts.length}件の投稿`, "day-posts"));
        const sources = element("p", undefined, "day-source");
        const seen = new Set();
        posts.forEach(row => row.sources.forEach(source => {
          if (seen.has(source.url)) return;
          seen.add(source.url);
          const a = element("a", `元の発表 ${seen.size} ↗`);
          a.href = source.url;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          sources.append(a);
        }));
        article.append(sources);
        target.append(article);
      });
      grid.querySelectorAll("[data-calendar-day]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.calendarDay === day)));
    };
    const render = () => {
      const [year, number] = month.value.split("-").map(Number);
      const firstDay = new Date(Date.UTC(year, number - 1, 1)).getUTCDay();
      const days = new Date(Date.UTC(year, number, 0)).getUTCDate();
      const cells = Math.ceil((firstDay + days) / 7) * 7;
      const fragment = document.createDocumentFragment();
      grid.setAttribute("aria-label", `${year}年${number}月`);
      for (let index = 0; index < cells; index++) {
        const date = index - firstDay + 1;
        if (date < 1 || date > days) {
          const empty = element("div", undefined, "calendar-empty");
          empty.setAttribute("aria-hidden", "true");
          fragment.append(empty);
          continue;
        }
        const key = `${month.value}-${String(date).padStart(2, "0")}`;
        const rows = records.get(key) || [];
        const button = element("button", undefined, "calendar-day" + (key === data.today ? " is-today" : ""));
        button.type = "button";
        button.dataset.calendarDay = key;
        button.setAttribute("aria-pressed", String(key === selected));
        button.setAttribute("aria-label", `${year}年${number}月${date}日、発表記録${rows.length}件` + (key === data.predicted ? "、予想日" : ""));
        button.append(element("span", date, "day-number"));
        const marks = element("span", undefined, "day-marks");
        if (rows.some(row => row.kind === "global")) marks.append(element("span", "リセット", "day-mark reset-mark"));
        if (rows.some(row => row.kind === "banked")) marks.append(element("span", "チケット", "day-mark banked-mark"));
        if (key === data.predicted) marks.append(element("span", "予想", "day-mark predicted-mark"));
        button.append(marks);
        button.addEventListener("click", () => details(key));
        fragment.append(button);
      }
      grid.replaceChildren(fragment);
      previous.disabled = month.value === data.first;
      next.disabled = month.value === data.last;
    };
    const changeMonth = () => {
      if (!selected.startsWith(month.value)) selected = data.records.find(row => row.day.startsWith(month.value))?.day || month.value + "-01";
      render();
      details(selected);
    };
    previous.addEventListener("click", () => { month.selectedIndex--; changeMonth(); });
    next.addEventListener("click", () => { month.selectedIndex++; changeMonth(); });
    month.addEventListener("change", changeMonth);
    document.getElementById("calendar-today").addEventListener("click", () => {
      month.value = data.today.slice(0, 7);
      selected = data.today;
      changeMonth();
    });
    render();
    details(selected);
    const forecastPanel = document.querySelector(".forecast-panel");
    if (forecastPanel) {
      const expire = () => {
        const editorialExpiry = forecastPanel.dataset.editorialExpiresAt;
        const numericForecast = document.getElementById("forecast-current");
        const age = numericForecast ? Date.now() - new Date(numericForecast.dataset.generatedAt).getTime() : 0;
        const expired = editorialExpiry
          ? Date.now() >= new Date(editorialExpiry).getTime()
          : age > 24 * 60 * 60 * 1000 || age < -5 * 60 * 1000;
        forecastPanel.hidden = expired;
        if (expired && data.predicted) {
          data.predicted = null;
          render();
          details(selected);
        }
      };
      expire();
      setInterval(expire, 60000);
    }
  }
  const form = document.getElementById("filters");
  if (form) {
    const rows = [...document.querySelectorAll("[data-record]")];
    const headings = [...document.querySelectorAll("[data-month-heading]")];
    const evidenceButtons = [...document.querySelectorAll("[data-evidence-option]")];
    const monthLinks = [...document.querySelectorAll("[data-month-link]")];
    const kind = document.getElementById("kind-filter");
    const evidence = document.getElementById("evidence-filter");
    const month = document.getElementById("month-filter");
    const search = document.getElementById("search-filter");
    const filter = () => {
      let count = 0;
      const visibleMonths = new Set();
      const keyword = search.value.trim().toLocaleLowerCase("ja");
      rows.forEach(row => {
        const visible = (kind.value === "all" || row.dataset.kind === kind.value)
          && (evidence.value === "all" || row.dataset.evidence === evidence.value)
          && (month.value === "all" || row.dataset.month === month.value)
          && (!keyword || row.textContent.toLocaleLowerCase("ja").includes(keyword));
        row.hidden = !visible;
        if (visible) { count++; visibleMonths.add(row.dataset.month); }
      });
      headings.forEach(heading => { heading.hidden = !visibleMonths.has(heading.dataset.monthHeading); });
      evidenceButtons.forEach(button => { button.setAttribute("aria-pressed", String(button.dataset.evidenceOption === evidence.value)); });
      monthLinks.forEach(link => {
        if (link.dataset.monthLink === month.value) link.setAttribute("aria-current", "true");
        else link.removeAttribute("aria-current");
      });
      document.getElementById("result-count").textContent = `${count}件の記録を表示`;
      document.getElementById("no-results").hidden = count !== 0;
    };
    evidenceButtons.forEach(button => button.addEventListener("click", () => { evidence.value = button.dataset.evidenceOption; filter(); }));
    monthLinks.forEach(link => link.addEventListener("click", () => { month.value = link.dataset.monthLink; filter(); }));
    form.addEventListener("input", filter);
    form.addEventListener("change", filter);
    form.addEventListener("submit", event => event.preventDefault());
    form.addEventListener("reset", event => {
      event.preventDefault();
      kind.value = evidence.value = month.value = "all";
      search.value = "";
      filter();
    });
  }
})();
