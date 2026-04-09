## EN-supporter (Vercel/FastAPI版)

経腸栄養の製剤選択・投与計画を支援するWebアプリです。  
Vercel デプロイ向けに、`FastAPI + 静的フロントエンド` 構成にしています。

## 構成

- `api/index.py`: FastAPI API（製剤データ提供）
- `public/index.html`: フロントエンド（画面・計算ロジック）
- `data_formulas.csv`: 製剤マスタ
- `vercel.json`: Vercelルーティング設定

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


