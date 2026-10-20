(() => {
  "use strict";
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
