const WebSocket = require('ws');

const SIDE_PANEL_ID = process.argv[2] || 'CD0E7DBEC83CD08C0C9DCFA56CA23676';
const prompt = process.argv[3] || '테스트';

const ws = new WebSocket(`ws://127.0.0.1:18800/devtools/page/${SIDE_PANEL_ID}`);

ws.on('open', () => {
  // Step 1: 에디터 포커스 + 기존 내용 선택
  ws.send(JSON.stringify({
    id: 1,
    method: 'Runtime.evaluate',
    params: {
      expression: `(() => {
        const editor = document.querySelector('.ProseMirror');
        if (!editor) return 'editor not found';
        editor.focus();
        const sel = window.getSelection();
        sel.selectAllChildren(editor);
        return 'focused';
      })()`,
      returnByValue: true
    }
  }));
});

ws.on('message', (data) => {
  const msg = JSON.parse(data);

  if (msg.id === 1) {
    console.log('Step 1:', msg.result?.result?.value);
    // Step 2: 프롬프트 입력
    ws.send(JSON.stringify({
      id: 2,
      method: 'Input.insertText',
      params: { text: prompt }
    }));
  }

  if (msg.id === 2) {
    console.log('Step 2: prompt inserted');
    // Step 3: 전송 버튼 클릭
    setTimeout(() => {
      ws.send(JSON.stringify({
        id: 3,
        method: 'Runtime.evaluate',
        params: {
          expression: `(() => {
            const btn = document.querySelector('button[aria-label="메시지 보내기"]');
            if (btn && !btn.disabled) { btn.click(); return 'sent!'; }
            return 'button disabled or not found';
          })()`,
          returnByValue: true
        }
      }));
    }, 500);
  }

  if (msg.id === 3) {
    console.log('Step 3:', msg.result?.result?.value);
    ws.close();
  }
});

ws.on('error', (e) => console.log('ws error:', e.message));
setTimeout(() => process.exit(), 15000);
