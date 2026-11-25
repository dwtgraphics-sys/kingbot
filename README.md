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
