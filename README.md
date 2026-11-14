# 🤖 Friday - AI Voice, Group Admin & Broadcast Telegram Bot

Friday एक अत्याधुनिक AI वॉइस और टेक्स्ट एजेंट है जो **Google Gemini (Gemini 2.5 Flash / 2.0 Flash)** और **Cartesia AI (नेचुरल हिंदी वॉइस)** से संचालित होता है।

---

## ✨ मुख्य फीचर्स

1. **⚡ अल्ट्रा-फास्ट Gemini ब्रेन:** Google का सबसे लेटेस्ट व सबसे तेज़ मॉडल (`gemini-2.5-flash` / `gemini-2.0-flash`) विद ऑटोमैटिक फॉलबैक।
2. **✍️ टेक्स्ट बातचीत:** टेक्स्ट मैसेज भेजें, तुरंत समझदारी भरा टेक्स्ट रिप्लाई मिलेगा।
3. **🎙️ वॉइस-टू-वॉइस कन्वर्सेशन:** वॉइस नोट भेजें, बॉट आपकी बात सुनकर 100% नेचुरल हिंदी/हिंग्लिश आवाज़ (Siya/Sagar) में बोलकर वॉइस नोट में जवाब देगा।
4. **👥 ग्रुप चैट्स:** ग्रुप में Friday को `@botusername` या रिप्लाई करके बात कर सकते हैं।
5. **📢 चैनल्स & ग्रुप्स में ऑटो-रजिस्ट्रेशन:** जैसे ही बॉट किसी ग्रुप या चैनल में जुड़ता है, उसका डेटाबेस में ऑटोमैटिक रजिस्ट्रेशन हो जाता है।
6. **👑 ब्रॉडकास्ट & प्रमोशन सिस्टम (Owner Only):**
   - `/broadcast <मैसेज>` — सभी पर्सनल DMs, ग्रुप्स और चैनल्स में एक साथ प्रमोशन भेजें।
   - `/broadcast_groups` — केवल सभी ग्रुप्स में ब्रॉडकास्ट।
   - `/broadcast_channels` — केवल सभी चैनल्स में ब्रॉडकास्ट।
   - `/broadcast_users` — केवल सभी पर्सनल DMs में ब्रॉडकास्ट।
   - `/stats` — कुल रीच (DMs, Groups, Channels) देखें।
7. **🛡️ ग्रुप एडमिन टूल्स (Admin Only):**
   - `/admin` या `/promote` — किसी भी सदस्य को फुल राइट्स के साथ एडमिन बनाएं।
   - `/demote` — एडमिन अधिकार वापस लें।
   - `/banall` — ग्रुप के सभी सदस्यों को एक साथ बैन करें।
   - `/unbanall` — बैन हुए सभी सदस्यों को एक साथ अनबैन करें और रिस्ट्रिक्शंस हटाएं।
   - `/muteall` — पूरे ग्रुप को एक साथ म्यूट करें (केवल एडमिन बोल सकेंगे)।
   - `/unmuteall` — पूरे ग्रुप को तुरंत अनम्यूट करें।
   - `/clear` या `/purge [संख्या]` — चैट के मैसेज एक साथ साफ़ करें।
   - `/tagall [मैसेज]` — सभी सदस्यों को टैग बोट की तरह बैच (5-5) में टैग करें।
   - `/stoptag` या `/cancel` — चालू टैगिंग को तुरंत रोकें।
   - `/ban` और `/unban` — किसी सदस्य को व्यक्तिगत बैन/अनबैन करें।
   - `/mute` और `/unmute` — किसी सदस्य को व्यक्तिगत म्यूट/अनम्यूट करें।
   - `/pause` और `/resume` — ग्रुप में AI को चालू या पॉज़ करें।

---

## 📁 प्रोजेक्ट फाइल्स

| फाइल | विवरण |
| :--- | :--- |
| [bot.py](file:///Users/yash/Desktop/Python%20Code/Friday/bot.py) | मुख्य Telegram बॉट, ब्रॉडकास्ट इंजन, टैग बॉट व एडमिन कमांड्स |
| [ai_agent.py](file:///Users/yash/Desktop/Python%20Code/Friday/ai_agent.py) | Google Gemini 2.5 Flash हाई-स्पीड मल्टीमॉडल AI ब्रेन |
| [voice_engine.py](file:///Users/yash/Desktop/Python%20Code/Friday/voice_engine.py) | Cartesia AI (Siya/Sagar) + Edge-TTS वॉइस इंजन |
| [config.py](file:///Users/yash/Desktop/Python%20Code/Friday/config.py) | एनवायरनमेंट सेटिंग्स और क्रेडेंशियल्स लोडर |
| [requirements.txt](file:///Users/yash/Desktop/Python%20Code/Friday/requirements.txt) | सभी आवश्यक Python लाइब्रेरीज़ |
| [.env](file:///Users/yash/Desktop/Python%20Code/Friday/.env) | टोकन्स और API Keys |

---

## 🚀 बॉट को चालू (Run) करने का तरीका

टर्मिनल में रन करें:
```bash
source .venv/bin/activate
python bot.py
```
या सीधे:
```bash
.venv/bin/python bot.py
```
