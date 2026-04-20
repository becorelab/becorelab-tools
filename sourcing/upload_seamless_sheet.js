/**
 * 심리스 팬티 1688 소싱 데이터 → 구글 시트 업로드
 */
const { google } = require("googleapis");
const fs = require("fs");
const path = require("path");

const SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs";
const SHEET_NAME = "심리스팬티 소싱";
const KEY_PATH = path.join(__dirname, "analyzer", "becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json");

async function getSheets() {
  const auth = new google.auth.GoogleAuth({
    keyFile: KEY_PATH,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
  return google.sheets({ version: "v4", auth });
}

async function ensureSheet(sheets) {
  const meta = await sheets.spreadsheets.get({ spreadsheetId: SHEET_ID });
  const existing = meta.data.sheets.find(s => s.properties.title === SHEET_NAME);
  if (!existing) {
    await sheets.spreadsheets.batchUpdate({
      spreadsheetId: SHEET_ID,
      requestBody: {
        requests: [{ addSheet: { properties: { title: SHEET_NAME } } }],
      },
    });
    console.log(`워크시트 '${SHEET_NAME}' 생성 완료`);
  }
}

async function upload() {
  const sheets = await getSheets();
  await ensureSheet(sheets);

  // 데이터 로드
  const details = JSON.parse(fs.readFileSync(path.join(__dirname, "1688_seamless_details.json"), "utf8"));
  const lowprice = JSON.parse(fs.readFileSync(path.join(__dirname, "1688_seamless_lowprice.json"), "utf8"));
  const allItems = [...details, ...lowprice];

  const headers = [
    "라벨", "가격(¥)", "판매량", "MOQ", "셀러유형", "재구매율(%)",
    "평점", "제품명(영문)", "1688 링크", "비고"
  ];

  const rows = allItems.map(d => {
    const data = d.data;
    const retention = data.review && data.review.retention_rate
      ? (data.review.retention_rate * 100).toFixed(1)
      : "";
    const link = `https://detail.1688.com/offer/${data.id}.html`;
    const note = details.includes(d) ? "상세조사" : "저가추가";
    return [
      d.label || "",
      data.price || "",
      data.sold || 0,
      data.moq || "",
      data.seller_type || "",
      retention,
      data.level || "",
      (data.titleEn || "").substring(0, 80),
      link,
      note,
    ];
  });

  // 시트 초기화 후 헤더+데이터 입력
  await sheets.spreadsheets.values.clear({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!A:Z`,
  });

  await sheets.spreadsheets.values.update({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!A1`,
    valueInputOption: "USER_ENTERED",
    requestBody: { values: [headers, ...rows] },
  });

  console.log(`✅ 업로드 완료! ${rows.length}개 업체`);
  console.log(`🔗 https://docs.google.com/spreadsheets/d/${SHEET_ID}`);
}

upload().catch(console.error);
