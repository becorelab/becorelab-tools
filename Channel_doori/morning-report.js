/**
 * 두리 아침 보고 스크립트
 * Windows 작업 스케줄러에서 매일 05:30 실행
 * Claude Code 세션과 무관하게 독립 동작
 */

const https = require('https');
const http = require('http');

const BOT_TOKEN = '8621050278:AAE56VUp5v7X9TDrK27ykX_POsYNqDvwO6U';
const CHAT_ID = '8708718261';
const LOGISTICS_BASE = 'http://localhost:8082';

function fetchText(url) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    mod.get(url, { timeout: 15000 }, (res) => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => resolve(data));
    }).on('error', reject).on('timeout', () => reject(new Error('Timeout')));
  });
}

function sendTelegram(text) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ chat_id: CHAT_ID, text, parse_mode: 'HTML' });
    const req = https.request({
      hostname: 'api.telegram.org',
      path: `/bot${BOT_TOKEN}/sendMessage`,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }
    }, (res) => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => resolve(JSON.parse(data)));
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function main() {
  console.log('[두리 아침 보고]', new Date().toLocaleString('ko-KR'));

  let salesText = '데이터 없음';
  let inventoryText = '데이터 없음';

  try {
    salesText = await fetchText(`${LOGISTICS_BASE}/api/daily-report?format=text`);
  } catch (e) {
    console.error('매출 API 오류:', e.message);
  }

  try {
    inventoryText = await fetchText(`${LOGISTICS_BASE}/api/inventory-report?format=text`);
  } catch (e) {
    console.error('재고 API 오류:', e.message);
  }

  const message = `대표님~! 두리예요 💕 아침 보고 드릴게요!\n\n📊 <b>매출 현황</b>\n${salesText}\n\n📦 <b>재고 현황</b>\n${inventoryText}`;

  try {
    const result = await sendTelegram(message);
    if (result.ok) {
      console.log('텔레그램 전송 완료 ✅');
    } else {
      console.error('텔레그램 전송 실패:', result);
    }
  } catch (e) {
    console.error('텔레그램 오류:', e.message);
  }
}

main().catch(console.error);
