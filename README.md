# EN-supporter

経腸栄養の製剤選択・投与計画を支援するWebアプリです。  
Vercel デプロイ向けに、`FastAPI + 静的フロントエンド` 構成にしています。

## 構成

- `api/index.py`: FastAPI API（製剤データ提供）
- `public/index.html`: フロントエンド（画面・計算ロジック）
- `data_formulas.csv`: 製剤マスタ
- `vercel.json`: Vercelルーティング設定
- `app.py`: **Streamlit** 版（機能が多い。ローカルや Streamlit Cloud 向け。**Vercel 本番には含まれません**）

## 本番（Vercel）とローカルで画面が違うとき

`vercel.json` では **`api/index.py` と `public/` の静的ファイルだけ** がデプロイ対象です。  
そのため **`streamlit run app.py` で見ている画面は Vercel には反映されません。** 本番 URL は **`public/index.html` ベースの軽量版**です。

- **Vercel 上の見た目・挙動を変えたい:** `public/index.html`（必要なら `api/index.py`）を編集し、`main` に push する（Git 連携が有効なら自動デプロイ）。
- **Streamlit 版をクラウドで使いたい:** [Streamlit Community Cloud](https://streamlit.io/cloud) など、Streamlit 用のホスティングを別途用意する（Vercel だけでは `app.py` は動かしません）。
- push 済みなのに本番が古い: Vercel ダッシュボードで対象プロジェクトが **この GitHub リポジトリ・`main` ブランチ** と紐づいているか確認し、「Redeploy」やキャッシュクリア、ブラウザのスーパーリロードを試してください。

## ローカル実行

```bash
cd "/Users/aiyamayuuki/EN supporter"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000
```

別ターミナルで静的ファイルを配信:

```bash
cd "/Users/aiyamayuuki/EN supporter"
python -m http.server 3000
```

ブラウザで `http://localhost:3000/public/index.html` を開きます。

## GitHub公開

```bash
git init
git add .
git commit -m "Migrate to FastAPI + Vercel-ready frontend"
gh repo create <repo-name> --public --source=. --remote=origin --push
```

`--private` に変えると非公開で作成できます。

## Vercelデプロイ

```bash
npm i -g vercel
vercel
```

初回は対話プロンプトに従って設定してください。  
以後は `vercel --prod` で本番デプロイできます。

## 注意

- 現在の患者データ・投与記録はブラウザの `localStorage` に保存されます。
- 本ツールは診療判断の補助目的です。最終判断は臨床チームで行ってください。
