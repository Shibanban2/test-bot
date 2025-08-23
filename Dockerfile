# Node.js イメージを利用
FROM node:18

# 作業ディレクトリを設定
WORKDIR /app

# package.json と package-lock.json をコピー
COPY package*.json ./

# ライブラリをインストール
RUN npm install

# 残りのコードをコピー
COPY . .

# Bot を起動するコマンド
CMD ["node", "index.js"]
