"""Send ONE alert to the operator's own Telegram chat through his phone bot's token (the channel he uses for every
bot alert). Reads C:\\kals\\telegram.json (token + chat_id); prints nothing secret."""
import json, sys
sys.path.insert(0, r"C:\kals-repo\research")
import pinphone
cfg = json.load(open(pinphone.CONFIG, encoding="utf-8"))
chat = cfg.get("chat_id")
if not chat:
    raise SystemExit("no chat_id in the phone bot config -- not sent")
pinphone.Telegram(cfg["token"]).send(chat, sys.argv[1])
print("sent to the operator's phone bot chat")
