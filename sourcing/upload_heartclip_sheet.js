const { google } = require("googleapis");
const https = require("https");
const fs = require("fs");
const path = require("path");

const SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs";
const SHEET_NAME = "하트집게 소싱";
const KEY_PATH = path.join(__dirname, "analyzer", "becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json");
const TOKEN_CACHE = path.join(__dirname, ".elimapi_token.json");

const CNY_USD = 0.138;
const USD_KRW = 1450;

// 소싱앱과 동일한 EXW 수입원가 계산 로직
function calcImportCost(exwUnitCNY, qty) {
  if (!exwUnitCNY || !qty || exwUnitCNY <= 0 || qty <= 0) return null;
  const exwUnit   = exwUnitCNY * CNY_USD;
  const exwTotal  = exwUnit * qty;
  const inland    = exwTotal * 0.05;
  const fob       = exwTotal + inland;
  const freight   = exwTotal * 0.08;
  const insurance = exwTotal * 0.005;
  const cif       = fob + freight + insurance;
  const duty      = cif * 0.08;
  const vat       = (cif + duty) * 0.10;
  const customs   = 100;
  const total     = cif + duty + vat + customs;
  const unit      = total / qty;
  return {
    unitUSD: unit.toFixed(2),
    unitKRW: Math.round(unit * USD_KRW),
    totalUSD: total.toFixed(0),
    cif: cif.toFixed(0),
  };
}

function postJson(urlPath, body, token) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const headers = {
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(data),
      "Accept": "application/json",
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const opts = { hostname: "openapi.elim.asia", path: urlPath, method: "POST", headers };
    const req = https.request(opts, res => {
      let raw = "";
      res.on("data", c => raw += c);
      res.on("end", () => { try { resolve(JSON.parse(raw)); } catch (e) { resolve({ error: true, raw }); } });
    });
    req.on("error", reject);
    req.write(data);
    req.end();
  });
}

async function getToken() {
  const cached = JSON.parse(fs.readFileSync(TOKEN_CACHE, "utf8"));
  return cached.access_token;
}

async function getDetail(id, token) {
  return postJson("/v1/products/find", { id: String(id), platform: "alibaba", lang: "en" }, token);
}

async function upload() {
  const token = await getToken();
  const auth = new google.auth.GoogleAuth({ keyFile: KEY_PATH, scopes: ["https://www.googleapis.com/auth/spreadsheets"] });
  const sheets = google.sheets({ version: "v4", auth });

  // 이미지 검색 결과 로드 (상위 후보들)
  const searchData = JSON.parse(fs.readFileSync(path.join(__dirname, "1688_heart_clip_search.json"), "utf8"));
  const items = searchData.items || [];

  // 관련성 높은 상위 10개만 상세 조회 (실리콘 집게 카테고리)
  const targetIds = items.slice(0, 10).map(i => i.id);

  const headers = [
    "제품명(영문)", "가격(¥)", "가격($)",
    "MOQ", "판매량", "재구매율(%)", "평점", "셀러유형",
    "한국도착가(단가$)", "한국도착가(단가₩)", "계산기준(MOQ)",
    "가격티어(MOQ→¥)", "1688 링크",
  ];

  console.log(`상세 조회 시작: ${targetIds.length}개`);
  const rows = [];

  for (let i = 0; i < targetIds.length; i++) {
    const id = targetIds[i];
    console.log(`  [${i+1}/${targetIds.length}] ${id}`);
    const d = await getDetail(id, token);
    if (!d || d.error || !d.id) {
      console.log(`    스킵`);
      continue;
    }

    const price = d.price || (d.price_range?.[0]?.price);
    const moq = d.moq || 1;
    const retention = d.review?.retention_rate ? (d.review.retention_rate * 100).toFixed(1) : "";
    const tiers = (d.price_range || []).map(t => `MOQ${t.moq}→¥${t.price}`).join(" / ");
    const link = `https://detail.1688.com/offer/${d.id}.html`;

    // 한국 도착가: MOQ 기준으로 계산
    const cost = calcImportCost(price, moq);

    rows.push([
      (d.titleEn || "").substring(0, 80),
      price || "",
      price ? `$${(price * CNY_USD).toFixed(2)}` : "",
      moq,
      d.sold || 0,
      retention,
      d.level || "",
      d.seller_type || "",
      cost ? `$${cost.unitUSD}` : "",
      cost ? `₩${cost.unitKRW.toLocaleString()}` : "",
      cost ? `MOQ ${moq}개` : "",
      tiers,
      link,
    ]);

    await new Promise(r => setTimeout(r, 400));
  }

  // 시트 없으면 생성
  const meta = await sheets.spreadsheets.get({ spreadsheetId: SHEET_ID });
  const exists = meta.data.sheets.find(s => s.properties.title === SHEET_NAME);
  if (!exists) {
    await sheets.spreadsheets.batchUpdate({
      spreadsheetId: SHEET_ID,
      requestBody: { requests: [{ addSheet: { properties: { title: SHEET_NAME } } }] },
    });
    console.log(`시트 '${SHEET_NAME}' 생성 완료`);
  } else {
    await sheets.spreadsheets.values.clear({ spreadsheetId: SHEET_ID, range: `${SHEET_NAME}!A:Z` });
  }
  await sheets.spreadsheets.values.update({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!A1`,
    valueInputOption: "USER_ENTERED",
    requestBody: { values: [headers, ...rows] },
  });

  console.log(`\n✅ 업로드 완료! ${rows.length}개`);
  console.log(`💡 원가 계산 기준: EXW→내륙5%→해상8%→보험0.5%→관세8%→부가세10%→통관$100`);
  console.log(`💱 환율: CNY×0.138=USD / USD×1,450=KRW`);
  console.log(`🔗 https://docs.google.com/spreadsheets/d/${SHEET_ID}`);
}

upload().catch(console.error);
