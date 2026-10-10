"""Build a read-only static demo. Never reads the user's local database."""
import json
import shutil
import tempfile
from pathlib import Path
from demo import ACCOUNTS, PRODUCTS, seed
from store import connect, entries

ROOT = Path(__file__).resolve().parent

def build():
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        db = connect(Path(directory) / 'synthetic.sqlite3')
        try:
            seed(db)
            rows = entries(db, 'demo', '2026-09-01', '2026-09-30')
        finally:
            db.close()
    for name in ('index.html', 'app.js', 'style.css', 'preview.js'):
        shutil.copyfile(ROOT / 'static' / name, output / name)
    html = (output / 'index.html').read_text()
    html = html.replace('<script src="/app.js"', '<script src="/preview.js" defer></script><script src="/app.js"')
    html = html.replace('Локальная версия 0.1<small>Данные на этом компьютере', 'Демоверсия 0.1<small>Вымышленные данные')
    html = html.replace('Загружаем локальные данные', 'Загружаем демонстрационные данные')
    (output / 'index.html').write_text(html)
    payload = dict(accounts=ACCOUNTS, products=[dict(sku=p[0], name=p[1], category=p[2]) for p in PRODUCTS], entries=rows)
    (output / 'preview-data.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
    print('Static demo built: dist (synthetic data only)')

if __name__ == '__main__':
    build()
