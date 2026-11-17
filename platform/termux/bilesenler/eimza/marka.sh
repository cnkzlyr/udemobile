# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# shellcheck shell=bash
# marka.sh — telif / kimlik bildirimi (diger betikler tarafindan 'source' edilir)
CKZ_YAZAR="Av. Can KIZILYAR"
CKZ_SURUM="2.0"
CKZ_IZ="⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠"
ckz_satir() { printf '[UYAP-Termux %s] © 2026 %s — Tüm hakları saklıdır.%s\n' "$CKZ_SURUM" "$CKZ_YAZAR" "$CKZ_IZ"; }
ckz_banner() {
  cat <<BANNER
==============================================================
  UYAP-Termux Kurulum Paketi                        v$CKZ_SURUM
  © 2026 $CKZ_YAZAR — Tüm hakları saklıdır.$CKZ_IZ
  Bu yazılım Av. Can KIZILYAR tarafından geliştirilmiştir.
  RESMÎ DEĞİLDİR: T.C. Adalet Bakanlığı / UYAP / HAVELSAN /
  TÜBİTAK ile bağlantısı yoktur. Ayrıntı: LICENSE.txt, NOTICE.txt
==============================================================
BANNER
}
