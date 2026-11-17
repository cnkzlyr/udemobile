"""asistan.js süre motoru için referans değerler: avukatasistan/utils.calculate_deadlines çıktısı (JSON)."""
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "asistan" / "moduller" / "avukatasistan"))
from utils import calculate_deadlines  # noqa: E402

MERCILER = ["İstanbul 3. Asliye Hukuk Mahkemesi", "Ankara 2. İş Mahkemesi", "İzmir 5. İcra Dairesi", "İCRA HUKUK MAHKEMESİ",
            "Bakırköy 4. Asliye Ceza Mahkemesi", "Ağır Ceza Mahkemesi", "Cumhuriyet Başsavcılığı Soruşturma Bürosu",
            "Ankara 1. İdare Mahkemesi", "İstanbul Vergi Mahkemesi", "DANIŞTAY 10. DAİRE", "Ankara BİM 3. İdari Dava Dairesi",
            "Kadıköy Kira Tespit", "Yargıtay 9. Hukuk Dairesi", "Tüketici Mahkemesi", ""]
rnd = random.Random(42)
cikti = []
bas = datetime(2025, 1, 1, 0, 0)
for _ in range(600):
    g = bas + timedelta(minutes=rnd.randrange(0, 3 * 365 * 24 * 60))
    m = rnd.choice(MERCILER)
    d = calculate_deadlines(g, m)
    cikti.append({"gelis": g.strftime("%Y-%m-%dT%H:%M"), "merci": m, "gun": d["target_days"], "teblig": d["teblig_str"],
                  "d7": d["d7_str"], "d14": d["d14_str"], "d30": d["d30_str"], "hedef": d["target_str"], "etiket": d["target_label"]})
print(json.dumps(cikti, ensure_ascii=False))
