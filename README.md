# Kingbot

بوت للعبة Rise of Kingdoms يعمل على سيرفر Windows ويُدار من لوحة التحكم:
https://dwtgraphics-sys.github.io/kingbot-ui/

## الملفات
- `bot.py` الحلقة الرئيسية، `smart.py` المهام الذكية، `common.py` أدوات الشاشة والضغط، `control.py` قراءة الأوامر وإرسال الحالة.
- `builtin_templates/` صور الأزرار التي يتعرّف عليها البوت.
- `publish_ui.py` يرفع واجهة اللوحة إلى مستودع `kingbot-ui`.
- ملفات `.bat` و`.vbs` للتشغيل والمراقبة على السيرفر.

## الأسرار
رموز GitHub وتيليجرام تبقى على السيرفر فقط (`github_token.txt`, `telegram.txt`) ولا تُرفع هنا أبداً (انظر `.gitignore`).


## تعدد السيرفرات (v193)
- كل سيرفر يعرف نفسه من ملف محلي **غير مرفوع** على GitHub: `C:\RisBot\local_config.json`
  (انسخ `local_config.example.json`) أو `.env` بسطر `SERVER_ID=vps-02-pilot`.
- بدون الملف = `vps-01-main` (السيرفر الرئيسي، كما كان).
- مسارات كل سيرفر في `kingbot-syn/servers/index.json` (يقرؤها `server_config.py` كل 10 دقائق، مع نسخة محفوظة محلياً).
- التبديل بين الحسابات المجدولة داخل السيرفر = «تدوير الشخصيات» (`char_rotation`) في إعدادات ذلك السيرفر.
- المراقبة: `watchdog.ps1` كل دقيقتين يشغّل البوت إن توقف، ويعيد تشغيله إن تجمّد (لا نبض في `heartbeat.txt` لـ5 دقائق)؛
  والبوت نفسه يغلق اللعبة إذا علقت («لا تستجيب») 3 دقائق ثم يفتحها من جديد.
