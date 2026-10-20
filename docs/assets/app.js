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
      document.getElementById("selected-date").textContent = `${year}年${number}月${date}日の履歴`;
      const target = document.getElementById("selected-records");
      target.replaceChildren();
      if (day === data.predicted) {
        target.append(element("p", "この日は独自予測の参考日です。公式の実施予定ではありません。", "predicted-day-note"));
      }
      const rows = records.get(day) || [];
      if (!rows.length) target.append(element("p", "この日の履歴はありません。", "empty-day"));
      rows.forEach(row => {
        const article = element("article", undefined, "day-record");
        const time = element("p", `${row.time} `, "day-record-time");
        time.append(element("span", row.evidence));
        article.append(time, element("h4", row.title));
        if (row.note) article.append(element("p", row.note));
        const sources = element("p", undefined, "day-source");
        row.sources.forEach(source => {
          const a = element("a", source.label + " ↗");
          a.href = source.url;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          sources.append(a);
        });
        const a = element("a", "履歴の詳細");
        a.href = "#" + row.id;
        a.addEventListener("click", () => document.getElementById("filters").reset());
        sources.append(a);
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
        button.setAttribute("aria-label", `${year}年${number}月${date}日、履歴${rows.length}件` + (key === data.predicted ? "、独自予測の参考日" : ""));
        button.append(element("span", date, "day-number"));
        const marks = element("span", undefined, "day-marks");
        if (rows.some(row => row.kind === "global" && row.state !== "announced")) marks.append(element("span", "一斉", "day-mark reset-mark"));
        if (rows.some(row => row.kind === "banked" && row.state !== "announced")) marks.append(element("span", "配布", "day-mark banked-mark"));
        if (rows.some(row => row.state === "announced")) marks.append(element("span", "予告", "day-mark announced-mark"));
        if (key === data.predicted) marks.append(element("span", "独自予測", "day-mark predicted-mark"));
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
    const expire = () => {
      const prediction = document.getElementById("forecast-current");
      const age = Date.now() - new Date(prediction.dataset.generatedAt).getTime();
      const expired = age > 24 * 60 * 60 * 1000 || age < -5 * 60 * 1000;
      prediction.hidden = expired;
      document.getElementById("forecast-expired").hidden = !expired;
      if (expired && data.predicted) {
        data.predicted = null;
        render();
        details(selected);
      }
    };
    expire();
    setInterval(expire, 60000);
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
      document.getElementById("result-count").textContent = `${count}件を表示`;
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
  const health = document.querySelector("[data-health-url]");
  if (!health) return;
  const text = document.getElementById("health-text");
  const formatter = new Intl.DateTimeFormat("ja-JP", {timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false});
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  fetch(health.dataset.healthUrl, {cache: "no-store", signal: controller.signal, credentials: "omit"})
    .then(response => {if (!response.ok) throw new Error("health unavailable"); return response.json();})
    .then(status => {
      const checked = new Date(status.checked_at);
      const success = new Date(status.last_success_at || "");
      if (!Number.isFinite(checked.getTime())) throw new Error("invalid health date");
      if (status.feed === "bootstrap") {
        text.textContent = "初期データを掲載しています。自動更新は未確認です。";
        health.classList.add("warn");
      } else if (status.feed === "ok" && Date.now() - checked.getTime() < 24 * 60 * 60 * 1000) {
        text.textContent = `最終更新：${formatter.format(checked)}（日本時間）`;
      } else {
        const last = Number.isFinite(success.getTime()) ? formatter.format(success) + "（日本時間）" : "未確認";
        text.textContent = `最新情報の取得を確認できません。前回の履歴を表示しています。最終取得：${last}`;
        health.classList.add("warn");
      }
    }).catch(() => {
      text.textContent += " 更新状況を取得できません。";
    }).finally(() => clearTimeout(timer));
})();
