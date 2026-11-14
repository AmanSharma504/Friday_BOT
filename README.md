# 🤖 Friday - AI Voice & Group Admin Telegram Bot

Friday एक अत्याधुनिक AI वॉइस और टेक्स्ट एजेंट है जो Google Gemini (3.1 Flash Lite) और Cartesia AI (नेचुरल हिंदी वॉइस) से संचालित होता है।

---

## ✨ मुख्य फीचर्स

1. **⚡ अल्ट्रा-फास्ट रिस्पॉन्स:** 2 से 4 सेकंड में तुरंत रिप्लाई (टेक्स्ट और वॉइस)।
2. **🎙️ 100% नेचुरल ह्यूमन हिंदी एक्सेंट:** Cartesia AI की **Siya** और **Sagar** आवाज़ें।
3. **👥 ग्रुप सपोर्ट:** ग्रुप में Friday को `@Itachi_X_Friday_bot` टैग करने या उसके मैसेज पर रिप्लाई करने पर तुरंत रिस्पॉन्स।
4. **🛡️ ग्रुप एडमिन टूल्स (Admin Only):**
   - `/tagall [मैसेज]` — सभी सदस्यों को टैग करना
   - `/ban` और `/unban` — सदस्यों को बैन/अनबैन करना
   - `/mute` और `/unmute` — म्यूट/अनम्यूट करना
   - `/promote` और `/demote` — एडमिन बनाना/हटाना
   - `/purge [संख्या]` — चैट तुरंत साफ़ करना
   - `/pause` और `/resume` — ग्रुप में AI पॉज़/चालू करना
5. **🧠 ऑटो-मेमोरी क्लियर:** 30 मिनट की इनएक्टिविटी के बाद अपने आप मेमोरी रीसेट ताकि सर्वर पर लोड न पड़े।

---

## 📁 प्रोजेक्ट फाइल्स

| फाइल | विवरण |
| :--- | :--- |
| **`bot.py`** | मुख्य Telegram बॉट और एडमिन कमांड्स |
| **`ai_agent.py`** | Gemini 3.1 Flash Lite हाई-स्पीड AI ब्रेन |
| **`voice_engine.py`** | Cartesia AI (Siya/Sagar) + Edge-TTS वॉइस इंजन |
| **`config.py`** | एनवायरनमेंट सेटिंग्स लोडर |
| **`requirements.txt`** | सभी आवश्यक Python लाइब्रेरीज़ |
| **`Procfile`** | क्लाउड वर्कर कमांड (`worker: python3 bot.py`) |
| **`Dockerfile`** | डोकर कंटेनर डिप्लॉयमेंट |
| **`render.yaml`** | Render.com 1-क्लिक डिप्लॉयमेंट ब्लूप्रिंट |
| **`Friday_Bot_Deploy.zip`** | पूरी प्रोजेक्ट का रेडी-टू-अपलोड जिप पैकेज |

---

## 🌐 24/7 फ्री क्लाउड होस्टिंग गाइड (बिना Mac चालू रखे)

### क्या Zip सीधे चल सकती है?
- **GitHub** पर Zip सीधे रन नहीं होती। GitHub पर आपको फाइल्स को ड्रैग करके (या Unzip करके) डालना होता है।
- **Render / Railway / Koyeb** पर आप अपनी GitHub रिपॉजिटरी कनेक्ट करके बॉट को 24/7 फ्री में चला सकते हैं।

### 3 आसान स्टेप्स में डिप्लॉय करें:

#### स्टेप 1: GitHub पर फाइल्स डालें
1. [GitHub.com](https://github.com/) पर जाएं और लॉगिन करें।
2. **"New repository"** पर क्लिक करें -> नाम रखें `friday-telegram-bot` -> **Public** या **Private** चुनें -> **Create repository** दबाएं।
3. पेज पर **"uploading an existing file"** पर क्लिक करें।
4. [Friday फ़ोल्डर](file:///Users/yash/Desktop/Python%20Code/Friday) की सभी फाइल्स को ड्रैग करके ड्रॉप कर दें (सिवाय `.venv` के)।
5. नीचे **"Commit changes"** दबाएं।

#### स्टेप 2: Render.com पर फ्री में होस्ट करें
1. [Render.com](https://render.com/) पर जाएं और अपने GitHub अकाउंट से साइन-अप करें।
2. **"New +"** बटन दबाएं और **"Background Worker"** (या Web Service) चुनें।
3. अपनी `friday-telegram-bot` रिपॉजिटरी को सेलेक्ट करें।
4. सेटिंग्स:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python3 bot.py`
5. **Environment Variables** में अपने 3 टोकन ऐड करें:
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `CARTESIA_API_KEY`
6. **"Create Work Service"** पर क्लिक करें!

बस! आपका Friday बॉट क्लाउड पर 24/7 बिना किसी रुकावट के चलता रहेगा, भले ही आपका Mac बंद हो!
# Friday_BOT
