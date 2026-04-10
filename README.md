# EN-supporter

経腸栄養の製剤選択・投与計画を支援するツールです。

## 開発の正（最新版）

**ローカルで触っている `app.py`（Streamlit）が機能の最新版です。**  
ここを主に編集し、GitHub の `main` に push して本番へ反映します。

## GitHub に commit → Vercel に反映（本番の仕様）

**`main` ブランチへ push すると、Vercel の本番が更新される**運用にします。次の **どちらか一方** を選んでください（両方有効にすると同じ push で二重デプロイになります）。

### 方法 A: Vercel の Git 連携（推奨・手軽）

1. [Vercel](https://vercel.com) にログイン → **Add New Project** → この GitHub リポジトリを選択  
2. **Production Branch** を `main` にする  
3. 以降は **commit → `main` へ push** だけで Vercel が自動ビルド・本番反映  

追加の GitHub Secrets は不要です。

### 方法 B: GitHub Actions からデプロイ（CI を明示したい場合）

リポジトリに [`.github/workflows/deploy-vercel.yml`](.github/workflows/deploy-vercel.yml) を同梱しています。

1. Vercel の **Account Settings → Tokens** でトークンを作成  
2. Vercel プロジェクトの **Settings → General** で **Project ID**、チームの **Team ID（Org ID）** を控える  
3. GitHub リポジトリ → **Settings → Secrets and variables → Actions** で次を登録  
   - `VERCEL_TOKEN`  
   - `VERCEL_ORG_ID`  
   - `VERCEL_PROJECT_ID`  
4. **Settings → Secrets and variables → Actions → Variables** で  
   - `VERCEL_DEPLOY_VIA_ACTIONS` = `true`  
5. **Vercel 側の「Git 連携による自動デプロイ」をオフ**にする（Actions と二重にならないように）

`VERCEL_DEPLOY_VIA_ACTIONS` を `true` にしていない限り、このワークフローはスキップされ、他環境で CI が落ちません。

---

| 本番の種類 | 中身 | `main` に push すると |
|------------|------|------------------------|
| **Vercel** | ルートの `index.html` + `api/index.py` + `data_formulas.csv` など | 上記 A または B で自動反映 |
| **Streamlit Community Cloud**（任意・フル機能） | `app.py` + 同梱 CSV | Cloud に接続済みなら自動再デプロイ |

**Vercel 上では Streamlit は動きません。** フル機能を URL で出す場合は **Streamlit Community Cloud** を別途接続してください。

### いつもの手順（ローカル → commit → 本番）

1. **`app.py`** を編集（必要なら `data_formulas.csv` や ルートの `index.html` も）。  
2. ローカル確認: `pip install -r requirements.txt` のうえ `streamlit run app.py`  
3. **commit して `main` に push** → Vercel が（A または B で）更新  
4. Streamlit Cloud を使っている場合は、同じ push で **Cloud 側も**更新される

### Streamlit Community Cloud（初回だけ）

1. [Streamlit Community Cloud](https://streamlit.io/cloud) にサインイン
2. GitHub リポジトリ **このプロジェクト** を選択
3. **Main file path**: `app.py`、**Branch**: `main`
4. デプロイ完了後に表示される URL（例: `https://xxx.streamlit.app`）を控える
5. （任意）ルートの **`index.html`** 内の **`STREAMLIT_APP_URL`** にその URL を貼り、push すると Vercel の軽量版からフル版へリンクが出ます

## 構成

- **`app.py`**: Streamlit 版（**本番フル機能の正**）
- **`api/index.py`**: FastAPI（製剤 API、`/api/formulas`）
- **`index.html`**（リポジトリ直下）: Vercel 向け軽量フロント（`localStorage` 利用）
- **`data_formulas.csv`**: 製剤マスタ（API・Streamlit 双方で参照）
- **`vercel.json`**: Vercel ルーティング
- **`.github/workflows/deploy-vercel.yml`**: （任意）Actions 経由で Vercel 本番へデプロイ

## ローカル実行（Streamlit・最新版）

```bash
cd "/path/to/EN supporter"
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Vercel の Python 関数は **`api/requirements.txt`**（軽量）を参照します。ルートの `requirements.txt` は Streamlit 用の依存を含みます。

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

ブラウザで `http://localhost:3000/` または `http://localhost:3000/index.html` を開きます。

## Vercel CLI（手動デプロイ）

初回のみや検証用。通常は上記 **方法 A（Git 連携）** で十分です。

```bash
npm i -g vercel
vercel
```

## 注意

- `patients.csv` などは `.gitignore` されているため、**Streamlit Cloud ではリポジトリに含まれる CSV のみ**がそのまま使われます。ローカル専用データは本番に上がりません。
- 本ツールは診療判断の補助目的です。最終判断は臨床チームで行ってください。
