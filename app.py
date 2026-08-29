from flask import Flask, render_template, jsonify
import requests
import os
from datetime import datetime, timezone
import json

app = Flask(__name__)

# ====================== إعدادات ======================
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens"
CACHE = {"tokens": [], "ai_summary": "", "updated_at": None}

# ====================== جلب بيانات حقيقية من DexScreener ======================
def fetch_new_meme_coins():
    try:
        # نجيب أحدث البولز على Solana (أشهر شبكة للميم كوينز)
        url = "https://api.dexscreener.com/token-boosts/top/v1"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=15)
        data = res.json()

        tokens = []
        for item in data[:30]:  # أول 30 عملة
            token = item.get("token", {}) or item
            chain = item.get("chainId") or token.get("chainId")
            if chain not in ["solana", "base", "ethereum"]:
                continue

            address = token.get("address") or item.get("tokenAddress")
            if not address:
                continue

            # نجيب تفاصيل أكثر
            detail_url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
            try:
                detail = requests.get(detail_url, headers=headers, timeout=10).json()
                pairs = detail.get("pairs") or []
                if not pairs:
                    continue
                pair = pairs[0]

                liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                volume = float(pair.get("volume", {}).get("h24", 0) or 0)
                change = float(pair.get("priceChange", {}).get("h24", 0) or 0)
                created = pair.get("pairCreatedAt")
                age_hours = None
                if created:
                    age_hours = round((datetime.now(timezone.utc).timestamp() * 1000 - created) / 3600000, 1)

                # فلترة أساسية: سيولة معقولة + حجم
                if liquidity < 5000 or volume < 1000:
                    continue

                tokens.append({
                    "symbol": pair.get("baseToken", {}).get("symbol", "???"),
                    "name": pair.get("baseToken", {}).get("name", "Unknown"),
                    "address": address,
                    "chain": chain,
                    "liquidity": int(liquidity),
                    "volume_24h": int(volume),
                    "change_24h": round(change, 1),
                    "age_hours": age_hours,
                    "url": pair.get("url") or f"https://dexscreener.com/{chain}/{address}",
                    "price": pair.get("priceUsd")
                })
            except:
                continue

        # نرتب حسب الحجم
        tokens = sorted(tokens, key=lambda x: x["volume_24h"], reverse=True)[:12]
        return tokens

    except Exception as e:
        print("Error fetching coins:", e)
        return []


# ====================== تحليل بالذكاء الاصطناعي (Grok) ======================
def analyze_with_ai(tokens):
    if not tokens:
        return "لا توجد عملات مناسبة حالياً. حاول مرة أخرى لاحقاً."

    if not XAI_API_KEY:
        return "تم فلترة العملات بنجاح، لكن مفتاح الذكاء الاصطناعي غير موجود. أضف XAI_API_KEY في إعدادات Render."

    try:
        prompt = "أنت محلل ميم كوينز محترف. هذه قائمة عملات جديدة تم فلترتها:\n\n"
        for i, t in enumerate(tokens[:8], 1):
            prompt += f"{i}. {t['symbol']} ({t['name']}) | السيولة: ${t['liquidity']:,} | الحجم 24س: ${t['volume_24h']:,} | التغيير: {t['change_24h']}% | العمر: {t['age_hours']} ساعة\n"

        prompt += "\nاختر أفضل 3 عملات فقط ورتبها، واكتب سبب قصير لكل واحدة بالعربية. كن صريحاً وحذراً."

        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json"
        }
        body = {
            "model": "grok-3",
            "messages": [
                {"role": "system", "content": "أنت محلل عملات مشفرة متخصص في الميم كوينز. أجب بالعربية فقط."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4
        }

        res = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=30
        )
        result = res.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print("AI Error:", e)
        return "حدث خطأ في تحليل الذكاء الاصطناعي. البيانات المفلترة موجودة تحت."


# ====================== المسارات ======================
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/results")
def results():
    return jsonify({
        "tokens": CACHE["tokens"],
        "ai_summary": CACHE["ai_summary"],
        "updated_at": CACHE["updated_at"]
    })


@app.route("/api/refresh")
def refresh():
    tokens = fetch_new_meme_coins()
    ai_summary = analyze_with_ai(tokens)

    CACHE["tokens"] = tokens
    CACHE["ai_summary"] = ai_summary
    CACHE["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    return jsonify({
        "tokens": tokens,
        "ai_summary": ai_summary,
        "updated_at": CACHE["updated_at"]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
