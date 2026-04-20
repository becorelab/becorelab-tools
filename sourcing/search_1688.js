const https = require("https");
const fs = require("fs");
const path = require("path");

const BASE_URL = "openapi.elim.asia";
const TOKEN_CACHE = path.join(__dirname, ".elimapi_token.json");
const EMAIL = "info@becorelab.kr";
const PASSWORD = "becolab@2026!!";

function postJson(urlPath, body, token) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const headers = {
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(data),
      "Accept": "application/json",
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const options = { hostname: BASE_URL, path: urlPath, method: "POST", headers };
    const req = https.request(options, res => {
      let raw = "";
      res.on("data", c => raw += c);
      res.on("end", () => {
        try { resolve(JSON.parse(raw)); } catch (e) { resolve({ error: true, raw }); }
      });
    });
    req.on("error", reject);
    req.write(data);
    req.end();
  });
}

async function login() {
  if (fs.existsSync(TOKEN_CACHE)) {
    const cached = JSON.parse(fs.readFileSync(TOKEN_CACHE, "utf8"));
    if (cached.access_token) return cached.access_token;
  }
  const result = await postJson("/v1/auth/login", { email: EMAIL, password: PASSWORD });
  if (result.access_token) {
    fs.writeFileSync(TOKEN_CACHE, JSON.stringify(result, null, 2), "utf8");
    return result.access_token;
  }
  throw new Error("Login failed: " + JSON.stringify(result));
}

async function search(keyword, page = 1, sort = "SALE_QTY_DESC") {
  const token = await login();
  const body = { q: keyword, platform: "alibaba", page, size: 20, lang: "en", sort };
  let result = await postJson("/v1/products/search", body, token);
  if (result.status === 401) {
    fs.unlinkSync(TOKEN_CACHE);
    const newToken = await login();
    result = await postJson("/v1/products/search", body, newToken);
  }
  return result;
}

async function main() {
  const keyword = process.argv[2] || "心形夹子 洗碗机";
  console.log(`🔍 1688 검색: "${keyword}"\n`);

  const result = await search(keyword);
  const items = result.items || result.data?.items || [];

  if (!items.length) {
    console.log("결과 없음. 응답:", JSON.stringify(result).substring(0, 500));
    return;
  }

  items.slice(0, 20).forEach((item, i) => {
    const usd = item.price ? `$${(item.price * 0.138).toFixed(2)}` : "";
    console.log(`${i+1}. [${item.id}] ¥${item.price} ${usd} | 판매량:${item.sales_volume||0} | ${item.titleEn?.substring(0,60) || item.title?.substring(0,60)}`);
    console.log(`   ${item.link || `https://detail.1688.com/offer/${item.id}.html`}`);
  });

  fs.writeFileSync(
    path.join(__dirname, "1688_last_result.json"),
    JSON.stringify({ keyword, result }, null, 2),
    "utf8"
  );
  console.log(`\n💾 결과 저장: 1688_last_result.json`);
}

main().catch(console.error);
