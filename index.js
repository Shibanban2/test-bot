import { Client, GatewayIntentBits } from "discord.js";
import fetch from "node-fetch";

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent],
});

const DISCORD_TOKEN = process.env.DISCORD_TOKEN;

// TSV を JSON に変換
function parseTSV(tsvText) {
  const lines = tsvText.trim().split("\n");
  const headers = lines[0].split("\t");
  return lines.slice(1).map(line => {
    const cols = line.split("\t");
    return headers.reduce((obj, header, i) => {
      obj[header] = cols[i] || "";
      return obj;
    }, {});
  });
}

client.on("messageCreate", async (message) => {
  if (message.author.bot) return;

  if (message.content.startsWith("sale ")) {
    const id = message.content.split(" ")[1];
    if (!id) return message.reply("IDを指定してください");

    try {
      // GitHub Pages の TSV 読み込み
      const res = await fetch("https://shibanban2.github.io/bc-event/token/sale.tsv");
      const tsv = await res.text();
      const data = parseTSV(tsv);

      // ID 検索
      const found = data.find(row => row.ID === id);
      if (!found) {
        return message.reply(`ID ${id} は見つかりませんでした`);
      }

      // 整形して返信
      const replyText = `[${found.ID} ${found.Name}]\n${found.Schedule}`;
      message.reply(replyText);

    } catch (err) {
      console.error(err);
      message.reply("データ取得でエラーが発生しました");
    }
  }
});

client.login(DISCORD_TOKEN);

