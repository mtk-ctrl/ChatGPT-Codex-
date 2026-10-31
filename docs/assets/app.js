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
    const pastPredictions = data.past_predictions || {};
    const outlook = data.outlook || {};
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
      if (outlook[day]) {
        const note = element("section", undefined, "calendar-outlook");
        note.append(element("h4", "今後の見通し（まだ発表されていません）"));
        note.append(element("p", outlook[day].possibility + "の可能性。 " + outlook[day].basis));
        note.append(element("p", "OpenAIの予定ではなく、サイトの推測です。"));
        target.append(note);
      }
      const oldForecasts = pastPredictions[day] || [];
      if (oldForecasts.length) {
        const summary = element("section", undefined, "calendar-past-predictions");
        summary.append(element("h4", `以前の予想（${oldForecasts.length}件）`));
        oldForecasts.forEach(item => {
          const text = `${item.published}に公開・${item.mark || "予想？"}（${item.status}）。 ${item.note}`;
          summary.append(element("p", text, "calendar-past-prediction-item"));
        });
        const back = element("a", "以前の予想とその理由を見る");
        back.href = "#previous-predictions-title";
        summary.append(back);
        target.append(summary);
      }
      const rows = records.get(day) || [];
      if (!rows.length) target.append(element("p", "この日のリセット発表は登録されていません。発表がなかったことを意味するものではありません。", "empty-day"));
      ["global", "banked"].forEach(kind => {
        const posts = rows.filter(row => row.kind === kind);
        if (!posts.length) return;
        const article = element("article", undefined, "day-record");
        article.append(element("h4", kind === "global" ? "リセット" : "リセットチケット"));
        article.append(element("p", `${posts.length}件の投稿`, "day-posts"));
        const sources = element("p", undefined, "day-source");
        [...posts].sort((a, b) => a.time.localeCompare(b.time)).forEach(row => {
          const source = row.sources[row.sources.length - 1];
          if (!source) return;
          const caption = kind === "global" ? "リセットの発表" : "チケット配布の発表";
          const a = element("a", `${row.time}｜${caption}（Xの投稿） ↗`);
          a.href = source.url;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          sources.append(a);
        });
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
        const historyLabels = (pastPredictions[key] || []).map(item => item.mark).join("、");
        button.setAttribute("aria-label", `${year}年${number}月${date}日、発表記録${rows.length}件` + (key === data.predicted ? "、予想中" : "") + (historyLabels ? "、" + historyLabels : "") + (outlook[key] ? "、今後の見通し" : ""));
        button.append(element("span", date, "day-number"));
        const marks = element("span", undefined, "day-marks");
        if (rows.some(row => row.kind === "global")) marks.append(element("span", "リセット", "day-mark reset-mark"));
        if (rows.some(row => row.kind === "banked")) marks.append(element("span", "チケット", "day-mark banked-mark"));
        if (key === data.predicted) marks.append(element("span", "予想中", "day-mark predicted-mark"));
        if (outlook[key]) marks.append(element("span", "見通し", "day-mark outlook-mark"));
        (pastPredictions[key] || []).forEach(item => {
          const acceptedClasses = ["forecast-hit-mark", "forecast-miss-mark", "forecast-pending-mark"];
          const markClass = acceptedClasses.includes(item.mark_class) ? item.mark_class : "forecast-pending-mark";
          marks.append(element("span", item.mark || "予想？", "day-mark " + markClass));
        });
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
    document.querySelectorAll("a[data-calendar-jump]").forEach(anchor => {
      anchor.addEventListener("click", event => {
        const date = anchor.dataset.calendarJump;
        if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return;
        const targetMonth = date.slice(0, 7);
        if (!Array.from(month.options).some(option => option.value === targetMonth)) return;
        event.preventDefault();
        month.value = targetMonth;
        selected = date;
        render();
        details(date);
        document.getElementById("calendar-title").scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
    const forecastPanel = document.querySelector(".forecast-panel");
    if (forecastPanel) {
      const expire = () => {
        const editorialExpiry = forecastPanel.dataset.editorialExpiresAt;
        const numericForecast = document.getElementById("forecast-current");
        const age = numericForecast ? Date.now() - new Date(numericForecast.dataset.generatedAt).getTime() : 0;
        const expired = editorialExpiry
          ? Date.now() >= new Date(editorialExpiry).getTime()
          : age > 24 * 60 * 60 * 1000 || age < -5 * 60 * 1000;
        // Keep expired editorial forecasts visible until the next build archives them.
        // The site must never quietly erase a prediction or its result.
        if (expired && editorialExpiry) {
          forecastPanel.hidden = false;
          const heading = forecastPanel.querySelector("#forecast-title");
          if (heading) heading.textContent = "前回の予想（結果を確認中）";
          if (!forecastPanel.querySelector(".prediction-expired-note")) {
            const note = document.createElement("p");
            note.className = "prediction-expired-note";
            note.textContent = "予想日は終了しました。この予想を記録として残し、的中・不的中を検証します。";
            forecastPanel.append(note);
          }
        } else {
          forecastPanel.hidden = expired;
        }
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
