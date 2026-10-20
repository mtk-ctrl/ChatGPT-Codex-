(() => {
  "use strict";
  const form = document.getElementById("filters");
  if (form) {
    const rows = [...document.querySelectorAll("[data-record]")];
    const kind = document.getElementById("kind-filter");
    const evidence = document.getElementById("evidence-filter");
    const month = document.getElementById("month-filter");
    const search = document.getElementById("search-filter");
    const filter = () => {
      let count = 0;
      const keyword = search.value.trim().toLocaleLowerCase("ja");
      rows.forEach(row => {
        const visible = (kind.value === "all" || row.dataset.kind === kind.value)
          && (evidence.value === "all" || row.dataset.evidence === evidence.value)
          && (month.value === "all" || row.dataset.month === month.value)
          && (!keyword || row.textContent.toLocaleLowerCase("ja").includes(keyword));
        row.hidden = !visible;
        if (visible) count++;
      });
      document.getElementById("result-count").textContent = `${count}件を表示`;
      document.getElementById("no-results").hidden = count !== 0;
    };
    form.addEventListener("input", filter);
    form.addEventListener("change", filter);
    form.addEventListener("submit", event => event.preventDefault());
    form.addEventListener("reset", () => requestAnimationFrame(filter));
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
        text.textContent = "初期データを掲載中。定期更新の初回成功はまだ確認していません。";
        health.classList.add("warn");
      } else if (status.feed === "ok" && Date.now() - checked.getTime() < 24 * 60 * 60 * 1000) {
        text.textContent = `自動取得の最終成功：${formatter.format(checked)} JST。公式本文の確認状況は各行をご覧ください。`;
      } else {
        const last = Number.isFinite(success.getTime()) ? formatter.format(success) + " JST" : "未確認";
        text.textContent = `更新の確認が必要です。保存済みの履歴を掲載しています。最終成功：${last}`;
        health.classList.add("warn");
      }
    }).catch(() => {
      text.textContent += " 最新の自動取得状況は現在読み込めません。";
    }).finally(() => clearTimeout(timer));
})();
