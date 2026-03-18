/**
 * iLBiA EZAdmin Collector — Background Service Worker
 *
 * 트리거 방식:
 * 1) externally_connectable: 물류 대시보드에서 chrome.runtime.sendMessage(EXT_ID, {action: "start-collect"})
 * 2) URL 파라미터 감지: window.open('https://ka04.ezadmin.co.kr/template35.htm?template=I100&ilbia_collect=start')
 *
 * 수집 순서: I100(재고) → I500(출고) → DS00(매출)
 * 완료 후: localhost:8082/api/chrome-upload 에 POST 전송
 */

const BASE = "https://ka04.ezadmin.co.kr";
const API_ENDPOINT = "http://localhost:8082/api/chrome-upload";

let collecting = false;
let dashboardTabId = null;
let collectedData = {};

// ─── 1) 외부 메시지 수신 (externally_connectable) ───
chrome.runtime.onMessageExternal.addListener((msg, sender, sendResponse) => {
  console.log("[EZAdmin Collector] 외부 메시지:", msg, "from:", sender.tab?.url);

  if (msg.action === "start-collect") {
    if (collecting) {
      sendResponse({ status: "already-collecting" });
      return;
    }
    dashboardTabId = sender.tab?.id || null;
    sendResponse({ status: "started", extensionId: chrome.runtime.id });
    startCollection();
  }

  if (msg.action === "get-extension-id") {
    sendResponse({ extensionId: chrome.runtime.id });
  }

  return true; // keep channel open for async
});

// ─── 2) URL 파라미터 감지 (ilbia_collect=start) ───
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") return;
  if (!tab.url) return;

  try {
    const url = new URL(tab.url);
    if (url.hostname === "ka04.ezadmin.co.kr" && url.searchParams.get("ilbia_collect") === "start") {
      if (collecting) {
        console.log("[EZAdmin Collector] 이미 수집 중 — 무시");
        return;
      }
      console.log("[EZAdmin Collector] URL 파라미터로 수집 트리거 감지");
      // 대시보드 탭은 별도로 찾아야 함
      findDashboardTab().then(() => {
        startCollection(tabId);
      });
    }
  } catch (e) {
    // invalid URL, ignore
  }
});

// ─── 3) content.js에서 오는 내부 메시지 수신 ───
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // 진행 상태 메시지 → 대시보드 탭에 전달
  if (msg.type === "progress") {
    console.log(`[EZAdmin Collector] 진행: ${msg.step} / ${msg.status}`, msg);
    notifyDashboard(msg);
  }

  // 스크래핑 결과
  if (msg.type === "scrape-result") {
    console.log(`[EZAdmin Collector] 결과 수신: ${msg.scrapeType}, 데이터:`, msg.data ? "있음" : "없음");
    sendResponse({ received: true });
  }

  return true;
});

// ─── 대시보드 탭 찾기 ───
async function findDashboardTab() {
  try {
    const tabs = await chrome.tabs.query({ url: "http://localhost:8082/*" });
    if (tabs.length > 0) {
      dashboardTabId = tabs[0].id;
      console.log("[EZAdmin Collector] 대시보드 탭 발견:", dashboardTabId);
    }
  } catch (e) {
    console.log("[EZAdmin Collector] 대시보드 탭 검색 실패:", e);
  }
}

// ─── 대시보드에 진행 상태 알림 ───
function notifyDashboard(data) {
  if (!dashboardTabId) return;
  chrome.tabs.sendMessage(dashboardTabId, {
    type: "ezadmin-progress",
    ...data,
  }).catch(() => {
    // 대시보드 탭이 닫혔거나 content script가 없음
  });
}

// ─── 수집 시작 ───
async function startCollection(existingTabId = null) {
  if (collecting) return;
  collecting = true;
  collectedData = {};

  console.log("[EZAdmin Collector] === 수집 시작 ===");
  notifyDashboard({ type: "progress", step: "start", status: "collecting" });

  let tabId = existingTabId;

  try {
    // 기존 탭이 없으면 새 탭 생성
    if (!tabId) {
      const tab = await chrome.tabs.create({
        url: `${BASE}/template35.htm?template=I100`,
        active: false,
      });
      tabId = tab.id;
    }

    // Step 1: 재고 (I100)
    console.log("[EZAdmin Collector] Step 1: 재고 (I100)");
    notifyDashboard({ type: "progress", step: "inventory", status: "navigating" });
    await navigateAndWait(tabId, `${BASE}/template35.htm?template=I100`);
    const inventory = await executeScrape(tabId, "inventory");
    collectedData.inventory = inventory;
    console.log("[EZAdmin Collector] 재고 수집 완료:", typeof inventory === "object" ? Object.keys(inventory).length + "건" : inventory);

    // Step 2: 출고 (I500)
    console.log("[EZAdmin Collector] Step 2: 출고 (I500)");
    notifyDashboard({ type: "progress", step: "outbound", status: "navigating" });
    await navigateAndWait(tabId, `${BASE}/template35.htm?template=I500`);
    const outbound = await executeScrape(tabId, "outbound");
    collectedData.orders = outbound;
    console.log("[EZAdmin Collector] 출고 수집 완료:", Array.isArray(outbound) ? outbound.length + "건" : outbound);

    // Step 3: 매출 (DS00)
    console.log("[EZAdmin Collector] Step 3: 매출 (DS00)");
    notifyDashboard({ type: "progress", step: "sales", status: "navigating" });
    await navigateAndWait(tabId, `${BASE}/template35.htm?template=DS00`);
    const sales = await executeScrape(tabId, "sales");
    collectedData.sales = sales;
    console.log("[EZAdmin Collector] 매출 수집 완료");

    // 서버에 전송
    console.log("[EZAdmin Collector] 서버 전송 중...");
    notifyDashboard({ type: "progress", step: "upload", status: "sending" });
    await uploadToServer(collectedData);

    console.log("[EZAdmin Collector] === 수집 완료 ===");
    notifyDashboard({ type: "progress", step: "done", status: "complete", data: collectedData });

  } catch (err) {
    console.error("[EZAdmin Collector] 수집 오류:", err);
    notifyDashboard({ type: "progress", step: "error", status: "failed", error: err.message });
  } finally {
    collecting = false;
  }
}

// ─── 탭 네비게이션 + 로딩 완료 대기 ───
function navigateAndWait(tabId, url) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error("페이지 로딩 타임아웃 (30초)"));
    }, 30000);

    function listener(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        clearTimeout(timeout);
        // 추가 대기 (DOM 안정화)
        setTimeout(resolve, 1000);
      }
    }

    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.update(tabId, { url });
  });
}

// ─── content.js에 스크래핑 명령 전송 + 결과 대기 ───
function executeScrape(tabId, scrapeType) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error(`${scrapeType} 스크래핑 타임아웃 (180초)`));
    }, 180000); // 3분 타임아웃 (페이지네이션 포함)

    // 메시지 리스너 등록 (결과 수신)
    function resultListener(msg, sender) {
      if (sender.tab?.id === tabId && msg.type === "scrape-result" && msg.scrapeType === scrapeType) {
        chrome.runtime.onMessage.removeListener(resultListener);
        clearTimeout(timeout);
        if (msg.error) {
          reject(new Error(msg.error));
        } else {
          resolve(msg.data);
        }
      }
    }

    chrome.runtime.onMessage.addListener(resultListener);

    // content.js에 스크래핑 명령 전송
    chrome.tabs.sendMessage(tabId, {
      action: "scrape",
      type: scrapeType,
    }).catch(err => {
      chrome.runtime.onMessage.removeListener(resultListener);
      clearTimeout(timeout);
      reject(new Error(`content.js 메시지 전송 실패: ${err.message}`));
    });
  });
}

// ─── 서버 업로드 ───
async function uploadToServer(data) {
  try {
    const resp = await fetch(API_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "chrome-extension",
        timestamp: new Date().toISOString(),
        ...data,
      }),
    });
    const result = await resp.json();
    console.log("[EZAdmin Collector] 서버 응답:", result);
    return result;
  } catch (err) {
    console.error("[EZAdmin Collector] 서버 전송 실패:", err);
    // 전송 실패해도 수집 데이터는 유지
    notifyDashboard({
      type: "progress",
      step: "upload",
      status: "failed",
      error: err.message,
    });
    throw err;
  }
}

// ─── 확장프로그램 설치 시 ID 콘솔 출력 ───
chrome.runtime.onInstalled.addListener(() => {
  console.log("[iLBiA EZAdmin Collector] 설치됨! Extension ID:", chrome.runtime.id);
  console.log("[iLBiA EZAdmin Collector] 물류 대시보드에서 아래 코드로 호출:");
  console.log(`  chrome.runtime.sendMessage("${chrome.runtime.id}", {action: "start-collect"}, resp => console.log(resp));`);
  console.log(`  또는 URL: window.open("${BASE}/template35.htm?template=I100&ilbia_collect=start")`);
});
