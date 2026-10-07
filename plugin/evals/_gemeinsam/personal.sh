# Plan 4h: lane fixtures (team level, fictional). Usage: personal_daten sauber|unordentlich
personal_daten() {
  mkdir -p 07_Daten
  cp "$SLK_G/personal/$1/07_Daten/"*.csv 07_Daten/
  if [ -d "$SLK_G/personal/$1/00_Eingang" ]; then cp "$SLK_G/personal/$1/00_Eingang/"* 00_Eingang/; fi
}
