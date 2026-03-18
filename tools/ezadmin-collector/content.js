/**
 * iLBiA EZAdmin Collector — Content Script
 * 이지어드민 페이지(ka04.ezadmin.co.kr)에서 실행
 *
 * background.js로부터 {action: "scrape", type: "inventory"|"outbound"|"sales"} 메시지를 받아
 * 해당 페이지의 데이터를 추출하고 결과를 반환합니다.
 */

// ─────────────────────────────────────────
// 공통 헬퍼
// ─────────────────────────────────────────

function removePopups() {
  try {
    document.querySelectorAll(".blockUI").forEach(el => el.remove());
    document.querySelectorAll(".dim").forEach(el => el.remove());
  } catch (e) {
    // ignore
  }
}

function clickSearch() {
  // span.flip 중 텍스트 "검색"인 요소 클릭
  const spans = document.querySelectorAll("span.flip");
  for (const s of spans) {
    if (s.textContent.trim() === "검색") {
      const parent = s.parentElement;
      if (parent) parent.click();
      else s.click();
      return true;
    }
  }
  // 폴백: 버튼/input/a 중 "검색" 텍스트
  const all = document.querySelectorAll('button, input[type="button"], input[type="submit"], a, span');
  for (const b of all) {
    const t = (b.textContent || b.value || "").trim();
    if (t.startsWith("검색") && b.offsetWidth > 0) {
      b.click();
      return true;
    }
  }
  return false;
}

function setMaxPageSize() {
  const sels = document.querySelectorAll(".ui-pg-selbox");
  sels.forEach(sel => {
    const opts = [...sel.options];
    const maxOpt = opts[opts.length - 1];
    if (maxOpt) {
      sel.value = maxOpt.value;
      sel.dispatchEvent(new Event("change"));
    }
  });
}

function goNextPage() {
  const nextBtn = document.querySelector('.ui-pg-button [class*="seek-next"]');
  if (!nextBtn) return false;
  const parent = nextBtn.closest(".ui-pg-button, td");
  if (parent && !parent.classList.contains("ui-state-disabled")) {
    parent.click();
    return true;
  }
  return false;
}

function waitFor(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function parseNum(str) {
  return parseInt((str || "0").replace(/,/g, "")) || 0;
}

function formatDate(d) {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function sendProgress(step, status, extra = {}) {
  chrome.runtime.sendMessage({
    type: "progress",
    step,
    status,
    ...extra,
  });
}

// ─────────────────────────────────────────
// 메시지 수신 — background.js에서 스크래핑 명령
// ─────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action !== "scrape") return;

  console.log(`[EZAdmin Content] 스크래핑 시작: ${msg.type}`);

  (async () => {
    try {
      let data;
      switch (msg.type) {
        case "inventory":
          data = await scrapeInventory();
          break;
        case "outbound":
          data = await scrapeOutbound();
          break;
        case "sales":
          data = await scrapeSales();
          break;
        default:
          throw new Error(`알 수 없는 타입: ${msg.type}`);
      }

      console.log(`[EZAdmin Content] ${msg.type} 완료`);
      chrome.runtime.sendMessage({
        type: "scrape-result",
        scrapeType: msg.type,
        data,
      });
    } catch (err) {
      console.error(`[EZAdmin Content] ${msg.type} 오류:`, err);
      chrome.runtime.sendMessage({
        type: "scrape-result",
        scrapeType: msg.type,
        error: err.message,
        data: null,
      });
    }
  })();

  // 비동기 응답
  sendResponse({ accepted: true });
  return true;
});

// ─────────────────────────────────────────
// 재고현황 (I100)
// ─────────────────────────────────────────

async function scrapeInventory() {
  sendProgress("inventory", "waiting");
  await waitFor(4000);
  removePopups();

  sendProgress("inventory", "searching");
  clickSearch();
  await waitFor(6000);
  removePopups();

  sendProgress("inventory", "setting-page-size");
  setMaxPageSize();
  await waitFor(3000);

  sendProgress("inventory", "extracting");

  const tbl = document.getElementById("grid1") || document.querySelector(".ui-jqgrid-btable");
  if (!tbl) {
    sendProgress("inventory", "error", { error: "grid1 테이블 없음" });
    return {};
  }

  const rows = [...tbl.querySelectorAll("tr")];
  const result = {};
  let count = 0;

  rows.forEach(tr => {
    const codeCell = tr.querySelector('td[aria-describedby$="_key"]');
    const stockCell = tr.querySelector('td[aria-describedby$="_stock"]');
    if (!codeCell || !stockCell) return;

    const code = codeCell.textContent.trim();
    const stock = parseNum(stockCell.textContent);

    if (code && code.length > 2) {
      result[code] = {
        stock,
        updated: formatDate(new Date()),
      };
      count++;
    }
  });

  sendProgress("inventory", "done", { count });
  console.log(`[EZAdmin Content] 재고 ${count}건 수집`);
  return result;
}

// ─────────────────────────────────────────
// 재고수불부 (I500) — 출고+배송 수량
// ─────────────────────────────────────────

async function scrapeOutbound() {
  const DAYS = 90;

  sendProgress("outbound", "waiting");
  await waitFor(5000);
  removePopups();

  // 날짜 설정 (90일 전 ~ 오늘)
  sendProgress("outbound", "setting-dates");
  const today = new Date();
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - DAYS);
  const startStr = formatDate(startDate);
  const endStr = formatDate(today);

  // 날짜 input 찾아서 설정
  const allInputs = document.querySelectorAll("input");
  const datePattern = /^\d{4}-\d{2}-\d{2}$/;
  const dateInputs = [...allInputs].filter(el => datePattern.test(el.value.trim()));

  if (dateInputs.length >= 2) {
    dateInputs[0].value = startStr;
    dateInputs[1].value = endStr;
    console.log(`[EZAdmin Content] 날짜 설정: ${startStr} ~ ${endStr}`);
  } else {
    console.warn("[EZAdmin Content] 날짜 input 찾기 실패, 기본값으로 진행");
  }

  // 검색
  sendProgress("outbound", "searching");
  clickSearch();
  await waitFor(8000);
  removePopups();

  // 페이지 크기 최대
  setMaxPageSize();
  await waitFor(5000);

  // 페이지네이션하며 데이터 수집
  const allData = [];
  const maxPages = 50;

  for (let pg = 0; pg < maxPages; pg++) {
    sendProgress("outbound", "extracting", { page: pg + 1 });

    const pageData = extractOutboundPage();

    if (pageData.length === 0) {
      if (pg === 0) {
        console.warn("[EZAdmin Content] I500 첫 페이지 데이터 없음");
      }
      break;
    }

    allData.push(...pageData);
    console.log(`[EZAdmin Content] I500 페이지 ${pg + 1}: ${pageData.length}건 (누적 ${allData.length}건)`);

    if (!goNextPage()) {
      console.log(`[EZAdmin Content] I500 마지막 페이지 도달 (${allData.length}건)`);
      break;
    }

    await waitFor(4000);
    removePopups();
  }

  // 날짜+상품코드별 집계
  const agg = {};
  allData.forEach(o => {
    const key = `${o.date}|${o.code}`;
    if (agg[key]) {
      agg[key].qty += o.qty;
    } else {
      agg[key] = { date: o.date, code: o.code, qty: o.qty };
    }
  });
  const result = Object.values(agg);

  sendProgress("outbound", "done", { count: result.length, rawCount: allData.length });
  console.log(`[EZAdmin Content] 출고 원본 ${allData.length}건 → 집계 ${result.length}건`);
  return result;
}

function extractOutboundPage() {
  const tbl = document.getElementById("grid1") || document.querySelector(".ui-jqgrid-btable");
  if (!tbl) return [];

  const rows = [...tbl.querySelectorAll("tr")];
  const data = [];

  rows.forEach(tr => {
    const codeCell = tr.querySelector('td[aria-describedby="grid1_product_id"]');
    const dateCell = tr.querySelector('td[aria-describedby="grid1_crdate"]');
    const outCell = tr.querySelector('td[aria-describedby="grid1_stockout"]');
    const shipCell = tr.querySelector('td[aria-describedby="grid1_trans"]');

    if (!codeCell || !dateCell) return;

    const code = codeCell.textContent.trim();
    const d = dateCell.textContent.trim().substring(0, 10);
    const outQty = outCell ? parseNum(outCell.textContent) : 0;
    const shipQty = shipCell ? parseNum(shipCell.textContent) : 0;
    const totalQty = outQty + shipQty;

    if (code && code.length > 2 && d.length === 10 && totalQty > 0) {
      data.push({ date: d, code, qty: totalQty });
    }
  });

  return data;
}

// ─────────────────────────────────────────
// 확장주문검색2 (DS00) — 매출 데이터
// ─────────────────────────────────────────

async function scrapeSales() {
  sendProgress("sales", "waiting");
  await waitFor(5000);
  removePopups();

  // 어제 날짜 설정
  sendProgress("sales", "setting-dates");
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const targetDate = formatDate(yesterday);

  const startInput = document.getElementById("start_date");
  const endInput = document.getElementById("end_date");
  if (startInput) startInput.value = targetDate;
  if (endInput) endInput.value = targetDate;
  console.log(`[EZAdmin Content] 매출 날짜: ${targetDate}`);

  // 1차 검색
  sendProgress("sales", "searching");
  clickSearch();
  await waitFor(8000);
  removePopups();

  // 페이지 크기 최대 → 재검색
  setMaxPageSize();
  await waitFor(2000);
  clickSearch();
  await waitFor(6000);
  removePopups();

  // 페이지네이션하며 데이터 수집
  const allData = [];
  const maxPages = 20;

  for (let pg = 0; pg < maxPages; pg++) {
    sendProgress("sales", "extracting", { page: pg + 1 });

    const pageData = extractSalesPage();

    if (pageData.length === 0) {
      if (pg === 0) {
        console.warn("[EZAdmin Content] DS00 첫 페이지 데이터 없음");
      }
      break;
    }

    allData.push(...pageData);
    console.log(`[EZAdmin Content] DS00 페이지 ${pg + 1}: ${pageData.length}건 (누적 ${allData.length}건)`);

    if (!goNextPage()) {
      console.log(`[EZAdmin Content] DS00 마지막 페이지 도달 (${allData.length}건)`);
      break;
    }

    await waitFor(4000);
    removePopups();
  }

  // 채널별/상품별 집계
  const channelSummary = {};
  const productSummary = {};
  let totalAmount = 0;
  let totalSettlement = 0;

  allData.forEach(row => {
    const shop = row.shop;
    const code = row.code;

    // 채널별
    if (!channelSummary[shop]) {
      channelSummary[shop] = { count: 0, qty: 0, amount: 0, settlement: 0 };
    }
    channelSummary[shop].count += 1;
    channelSummary[shop].qty += row.productQty;
    channelSummary[shop].amount += row.amount;
    channelSummary[shop].settlement += row.settlement;

    // 상품별
    if (!productSummary[code]) {
      productSummary[code] = { name: row.nameOpt || row.name, qty: 0, amount: 0, settlement: 0 };
    }
    productSummary[code].qty += row.productQty;
    productSummary[code].amount += row.amount;
    productSummary[code].settlement += row.settlement;

    totalAmount += row.amount;
    totalSettlement += row.settlement;
  });

  const result = {
    date: targetDate,
    total_amount: totalAmount,
    total_settlement: totalSettlement,
    total_count: allData.length,
    by_channel: channelSummary,
    by_product: productSummary,
    orders: allData,
  };

  sendProgress("sales", "done", {
    count: allData.length,
    totalAmount,
    totalSettlement,
    channels: Object.keys(channelSummary).length,
  });

  console.log(`[EZAdmin Content] 매출 ${allData.length}건 수집 — 총 ${totalAmount.toLocaleString()}원`);
  return result;
}

function extractSalesPage() {
  const tbl = document.getElementById("grid1") || document.querySelector(".ui-jqgrid-btable");
  if (!tbl) return [];

  const rows = [...tbl.querySelectorAll("tr.jqgrow")];
  const data = [];

  rows.forEach(tr => {
    const get = key => {
      const td = tr.querySelector(`td[aria-describedby="grid1_${key}"]`);
      return td ? td.textContent.trim() : "";
    };

    const shop = get("shop_id");
    const dt = get("collect_date");
    const code = get("product_id");
    const name = get("name");
    const nameOpt = get("product_name_options");
    const option = get("p_options");
    const orderQty = parseNum(get("qty"));
    const productQty = parseNum(get("order_products_qty"));
    const amount = parseNum(get("amount"));
    const settlement = parseNum(get("supply_price"));
    const stock = parseNum(get("stock"));

    if (code) {
      data.push({
        shop,
        date: dt,
        code,
        name,
        nameOpt,
        option,
        orderQty,
        productQty,
        amount,
        settlement,
        stock,
      });
    }
  });

  return data;
}

// ─────────────────────────────────────────
// 초기화 로그
// ─────────────────────────────────────────
console.log("[iLBiA EZAdmin Collector] Content script 로드됨:", window.location.href);
