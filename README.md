# EN-supporter

経腸栄養の製剤選択・投与計画を支援するツールです。

## 開発の正（最新版）

**ローカルで触っている `app.py`（Streamlit）が機能の最新版です。**  
ここを主に編集し、GitHub の `main` に push して本番へ反映します。

| 本番の種類 | 中身 | `main` に push すると |
|------------|------|------------------------|
| **Streamlit Community Cloud**（推奨・フル機能） | `app.py` + 同梱 CSV | 自動で再デプロイ（初回のみ Cloud でリポジトリ接続） |
| **Vercel** | `public/index.html` + `api/index.py` + `data_formulas.csv` など | 自動で再デプロイ（Git 連携時） |

**Vercel 上では Streamlit は動きません。** フル機能を URL で出したい場合は、必ず **Streamlit Community Cloud** を併用してください（同じリポジトリでよい）。

### いつもの手順（ローカル開発 → 本番更新）

1. 機能は **`app.py`** を編集（必要なら `data_formulas.csv` や `public/index.html` も）。
2. ローカル確認: `pip install -r requirements.txt` のうえ `streamlit run app.py`
3. コミットして **`main` に push**
4. **Streamlit Cloud**: 接続済みなら数分で `app.py` 側が更新される  
5. **Vercel**: `public/` や `api/`・CSV を変えていれば同じ push で反映される

### Streamlit Community Cloud（初回だけ）

1. [Streamlit Community Cloud](https://streamlit.io/cloud) にサインイン
2. GitHub リポジトリ **このプロジェクト** を選択
3. **Main file path**: `app.py`、**Branch**: `main`
4. デプロイ完了後に表示される URL（例: `https://xxx.streamlit.app`）を控える
5. （任意）`public/index.html` 内の **`STREAMLIT_APP_URL`** にその URL を貼り、push すると Vercel の軽量版からフル版へリンクが出ます

## 構成

- **`app.py`**: Streamlit 版（**本番フル機能の正**）
- **`api/index.py`**: FastAPI（製剤 API、`/api/formulas`）
- **`public/index.html`**: Vercel 向け軽量フロント（`localStorage` 利用）
- **`data_formulas.csv`**: 製剤マスタ（API・Streamlit 双方で参照）
- **`vercel.json`**: Vercel ルーティング

## ローカル実行（Streamlit・最新版）

```bash
cd "/path/to/EN supporter"
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## ローカル実行（Vercel 構成の確認用）

API:

```bash
pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000
```

別ターミナルで静的ファイル:

```bash
python -m http.server 3000
```

ブラウザで `http://localhost:3000/public/index.html` を開きます。

## Vercel デプロイ

GitHub とプロジェクトを接続していれば **`main` への push で自動デプロイ**されます。  
CLI の場合:

```bash
npm i -g vercel
vercel
```

## 注意

- `patients.csv` などは `.gitignore` されているため、**Streamlit Cloud ではリポジトリに含まれる CSV のみ**がそのまま使われます。ローカル専用データは本番に上がりません。
- 本ツールは診療判断の補助目的です。最終判断は臨床チームで行ってください。
