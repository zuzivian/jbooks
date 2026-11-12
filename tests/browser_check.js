// Playwright smoke test of the static viewer: no console errors, no horizontal scroll,
// change view and charts render. Usage: node tests/browser_check.js http://localhost:8000 [screenshot-dir]
const { chromium } = require("playwright");
const base = process.argv[2] || "http://localhost:8000";
const shots = process.argv[3];
(async () => {
  const browser = await chromium.launch();
  let failed = false;
  for (const [w, h] of [[1280, 900], [390, 844]]) {
    for (const q of ["", "?demo=1"]) {
      const page = await browser.newPage({ viewport: { width: w, height: h } });
      const errors = [];
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(base + "/index.html" + q, { waitUntil: "networkidle" });
      await page.waitForSelector("#rows tr");
      if (!q) await page.waitForSelector("#svc-chart svg path");
      const r = await page.evaluate(() => ({
        scroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        findings: document.querySelectorAll("#findings-list li").length,
        bars: document.querySelectorAll("#svc-chart path, #cat-chart path").length,
        related: document.querySelectorAll("#related-rows tr").length,
        changesHidden: document.getElementById("changes").hidden,
      }));
      const bad = [];
      if (errors.length) bad.push("console errors: " + errors.join(" | "));
      if (r.scroll > 0) bad.push("horizontal scroll of " + r.scroll + "px");
      if (!q && (r.findings < 3 || r.findings > 5)) bad.push("expected 3-5 findings, got " + r.findings);
      if (!q && !r.bars) bad.push("charts did not render");
      if (!q && !r.related) bad.push("related table empty");
      if (q && !r.changesHidden) bad.push("change view should be hidden for synthetic demo");
      console.log(`${w}px ${q || "live"}: ${bad.length ? "FAIL " + bad.join("; ") : "ok"}`, JSON.stringify(r));
      if (bad.length) failed = true;
      if (shots && !q) await page.screenshot({ path: `${shots}/viewer-${w}.png`, fullPage: true });
      await page.close();
    }
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
