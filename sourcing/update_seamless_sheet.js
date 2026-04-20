const { google } = require("googleapis");
const fs = require("fs");
const path = require("path");

const SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs";
const SHEET_NAME = "심리스팬티 소싱";
const KEY_PATH = path.join(__dirname, "analyzer", "becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json");

const TARGET_IDS = ["864099764667","706759771264","619380574744","621237223885","661119231220","718654774706","650874827219"];

async function upload() {
  const auth = new google.auth.GoogleAuth({ keyFile: KEY_PATH, scopes: ["https://www.googleapis.com/auth/spreadsheets"] });
  const sheets = google.sheets({ version: "v4", auth });

  const details = JSON.parse(fs.readFileSync(path.join(__dirname, "1688_seamless_details.json"), "utf8"));
  const low = JSON.parse(fs.readFileSync(path.join(__dirname, "1688_seamless_lowprice.json"), "utf8"));
  const all = [...details, ...low].filter(d => TARGET_IDS.includes(String(d.data.id)));

  const headers = [
    "라벨", "가격(¥)", "$", "판매량", "MOQ", "셀러유형", "재구매율(%)", "평점",
    "색상 수", "색상 목록", "사이즈 범위", "가격 티어(MOQ→가격)",
    "소재 키워드", "1688 링크", "케이 검토"
  ];

  const rows = all.map(d => {
    const data = d.data;
    const retention = data.review?.retention_rate ? (data.review.retention_rate * 100).toFixed(1) : "";
    const usd = data.price ? (data.price * 0.138).toFixed(2) : "";

    const skus = data.skus || [];
    const colors = [...new Set(skus.map(s => s.options?.find(o => o.nameEn === "Color")?.valueEn).filter(Boolean))];
    const sizes = [...new Set(skus.map(s => s.options?.find(o => o.nameEn === "Size")?.valueEn).filter(Boolean))];

    const tiers = (data.price_range || []).map(t => `MOQ${t.moq}→¥${t.price}`).join(" / ");

    // 소재 키워드 타이틀에서 추출
    const title = data.titleEn || "";
    const materials = [];
    if (/ice silk/i.test(title)) materials.push("아이스실크");
    if (/cotton/i.test(title)) materials.push("면안감");
    if (/nylon/i.test(title)) materials.push("나일론");
    if (/modal/i.test(title)) materials.push("모달");

    const link = `https://detail.1688.com/offer/${data.id}.html`;

    return [
      d.label || "",
      data.price || "",
      usd ? `$${usd}` : "",
      data.sold || 0,
      data.moq || "",
      data.seller_type || "",
      retention,
      data.level || "",
      colors.length,
      colors.join(", "),
      sizes.join(", "),
      tiers,
      materials.join(", "),
      link,
      "형태 맞음",
    ];
  });

  await sheets.spreadsheets.values.clear({ spreadsheetId: SHEET_ID, range: `${SHEET_NAME}!A:Z` });
  await sheets.spreadsheets.values.update({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!A1`,
    valueInputOption: "USER_ENTERED",
    requestBody: { values: [headers, ...rows] },
  });

  console.log(`✅ 업데이트 완료! "형태 맞음" ${rows.length}개`);
  console.log(`🔗 https://docs.google.com/spreadsheets/d/${SHEET_ID}`);
}

upload().catch(console.error);
