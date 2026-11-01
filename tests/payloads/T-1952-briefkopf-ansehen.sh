cd "__WS__" && ls "06_Kunden" "Beispiel/06_Kunden/Hansa Pack AG" 2>&1; mkdir -p /tmp/hp && cp Beispiel/Unternehmen/vorlagen/briefkopf.docx /tmp/hp/briefkopf.docx && cd /tmp && uv run --with python-docx==1.1.2 python -I -c "
import docx
d=docx.Document('/tmp/hp/briefkopf.docx')
print([(p.style.name,p.text) for p in d.paragraphs])
print([ [p.text for p in s.header.paragraphs] for s in d.sections],[ [p.text for p in s.footer.paragraphs] for s in d.sections])
print(len(d.tables),[s.name for s in d.styles if s.type==1][:15])
"; sed -n 1,40p "__WS__/Beispiel/01_Vorgaenge/offen/V-0003.md" 2>/dev/null | head -5