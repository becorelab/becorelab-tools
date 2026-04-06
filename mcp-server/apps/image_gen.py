"""이미지 생성 MCP 도구 — Gemini (나노바나나) API"""

import base64
import json
import os
import time
import httpx

GEMINI_API_KEY = "AIzaSyD9QzFNwGKYgZ61hlDpFPXKDqd2d6ssiho"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "generated_images")


def register(mcp, client, base_url=None):

    @mcp.tool()
    async def generate_image(prompt: str = "", model: str = "gemini-2.5-flash", aspect: str = "16:9", save_name: str = "") -> str:
        """프롬프트로 이미지를 생성합니다 (나노바나나/Gemini API).
        대표님이 '이미지 만들어줘', '배너 생성해줘' 하면 이 도구 사용.

        prompt: 이미지 생성 프롬프트 (한국어 OK, 상세할수록 좋음)
        model: 'gemini-2.5-flash' (나노바나나, 기본) 또는 'gemini-2.5-pro' (프로, 고품질)
        aspect: 비율 — '16:9' (배너), '1:1' (정사각), '9:16' (세로), '4:3'
        save_name: 저장할 파일명 (생략하면 자동 생성)"""
        if not prompt:
            return "[오류] prompt를 입력해주세요."

        try:
            # 모델 선택
            if "pro" in model.lower():
                model_id = "gemini-2.5-pro-preview-06-05"
            else:
                model_id = "gemini-2.5-flash-preview-native-audio-dialog"

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"

            # 이미지 생성 요청
            body = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"Generate an image: {prompt}\n\nAspect ratio: {aspect}. High quality, professional."
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                },
            }

            async with httpx.AsyncClient(timeout=120) as http:
                resp = await http.post(url, json=body)
                data = resp.json()

            # 에러 체크
            if "error" in data:
                return f"[오류] Gemini API: {data['error'].get('message', str(data['error']))}"

            if "candidates" not in data:
                block_reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
                return f"[차단] 프롬프트가 안전 필터에 걸렸어요. 이유: {block_reason}"

            # 이미지 추출
            parts = data["candidates"][0]["content"]["parts"]
            image_data = None
            text_response = ""

            for part in parts:
                if "inlineData" in part:
                    image_data = part["inlineData"]["data"]
                    mime_type = part["inlineData"].get("mimeType", "image/png")
                elif "text" in part:
                    text_response = part["text"]

            if not image_data:
                return f"[실패] 이미지가 생성되지 않았어요. 텍스트 응답: {text_response[:300]}"

            # 파일 저장
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            if not save_name:
                save_name = f"img_{int(time.time())}"
            ext = "png" if "png" in mime_type else "jpg"
            file_path = os.path.join(OUTPUT_DIR, f"{save_name}.{ext}")

            with open(file_path, "wb") as f:
                f.write(base64.b64decode(image_data))

            return f"이미지 생성 완료!\n파일: {file_path}\n모델: {model}\n비율: {aspect}\n프롬프트: {prompt[:100]}...\n{text_response[:200] if text_response else ''}"

        except Exception as e:
            return f"[오류] 이미지 생성 실패: {e}"

    @mcp.tool()
    async def generate_banner(
        product: str = "",
        purpose: str = "상세페이지",
        main_copy: str = "",
        sub_copy: str = "",
        style: str = "깔끔하고 심플한",
        background: str = "soft pastel gradient",
    ) -> str:
        """이커머스 배너 이미지를 생성합니다 (상세페이지/카톡 배너 전용).
        대표님이 '배너 만들어줘', '상세페이지 이미지' 요청하면 이 도구 사용.

        product: 제품명 (예: 'iLBiA 건조기시트 코튼블루')
        purpose: '상세페이지' (860x500), '카톡배너' (720x360), '정사각' (720x720)
        main_copy: 메인 카피 (예: '매일 입는 옷에, 매일 좋은 향을')
        sub_copy: 서브 카피 (예: '프리미엄 건조기 시트')
        style: 스타일 (예: '깔끔하고 심플한', '고급스럽고 따뜻한', '밝고 경쾌한')
        background: 배경 (예: 'soft pastel blue', 'white studio', 'lifestyle kitchen')"""
        if not product:
            return "[오류] product(제품명)를 입력해주세요."

        # 용도별 비율
        aspect_map = {
            "상세페이지": "16:9",
            "카톡배너": "2:1",
            "정사각": "1:1",
        }
        aspect = aspect_map.get(purpose, "16:9")

        # 프롬프트 조합
        prompt_parts = [
            f"Professional e-commerce product banner for '{product}'.",
            f"Style: {style}, clean and modern.",
            f"Background: {background}.",
            "Product should be the hero element, prominently displayed.",
        ]

        if main_copy:
            prompt_parts.append(f"Leave clear space in the upper area for text overlay: '{main_copy}'.")
        if sub_copy:
            prompt_parts.append(f"Additional text space for: '{sub_copy}'.")

        prompt_parts.extend([
            "Professional studio lighting, high-end product photography feel.",
            "No text rendered in the image — only product and background.",
            "Korean household product brand, warm and trustworthy mood.",
        ])

        prompt = " ".join(prompt_parts)
        save_name = f"banner_{product.replace(' ', '_')}_{int(time.time())}"

        # generate_image 호출
        return await generate_image(
            prompt=prompt,
            model="gemini-2.5-flash",
            aspect=aspect,
            save_name=save_name,
        )

    @mcp.tool()
    async def list_generated_images() -> str:
        """생성된 이미지 목록을 보여줍니다."""
        try:
            if not os.path.exists(OUTPUT_DIR):
                return "생성된 이미지가 없어요."
            files = sorted(os.listdir(OUTPUT_DIR), reverse=True)
            if not files:
                return "생성된 이미지가 없어요."
            lines = [f"생성된 이미지 {len(files)}개:"]
            for f in files[:20]:
                path = os.path.join(OUTPUT_DIR, f)
                size_kb = os.path.getsize(path) // 1024
                lines.append(f"  {f} ({size_kb}KB)")
            return "\n".join(lines)
        except Exception as e:
            return f"[오류] {e}"
