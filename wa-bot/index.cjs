const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const axios = require("axios");

const API_URL = "http://127.0.0.1:8000/agent/whatsapp-web";

const activeUsers = new Set();

const client = new Client({
  authStrategy: new LocalAuth({
    clientId: "swiftvalet-agent"
  }),
  puppeteer: {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"]
  }
});

client.on("qr", (qr) => {
  console.log("Scan this QR with WhatsApp Linked Devices:");
  qrcode.generate(qr, { small: true });
});

client.on("ready", () => {
  console.log("SwiftValet WhatsApp bot is ready!");
});

client.on("message", async (msg) => {
  try {
    const senderId = msg.from;
    const text = msg.body || "";
    const lowerText = text.toLowerCase().trim();

    if (
      senderId.includes("@g.us") ||
      senderId.includes("status@broadcast") ||
      senderId.includes("@newsletter")
    ) {
      return;
    }

    // Only start flow when user sends reset
    if (lowerText === "reset" || lowerText === "get my car") {
  activeUsers.add(senderId);
}

if (!activeUsers.has(senderId)) {
  return;
}

    console.log("MESSAGE RECEIVED:", senderId, text);

    let mediaBase64 = null;
    let mimeType = null;

    if (msg.hasMedia) {
      const media = await msg.downloadMedia();
      mediaBase64 = media.data;
      mimeType = media.mimetype;
    }

    console.log("CALLING FASTAPI...");

    const response = await axios.post(
      API_URL,
      {
        from: senderId,
        body: text,
        hasMedia: msg.hasMedia,
        mediaBase64: mediaBase64,
        mimeType: mimeType
      },
      {
        timeout: 180000
      }
    );

    console.log("FASTAPI RESPONSE:", response.data);

    if (response.data.reply) {
      await client.sendMessage(senderId, response.data.reply);
    }

    if (response.data.sendTo && response.data.message) {
      let target = response.data.sendTo;

      if (!target.includes("@")) {
        target = target + "@c.us";
      }

      await client.sendMessage(target, response.data.message);
    }

  } catch (err) {
    console.error("BOT ERROR:", err.message);
  }
});

client.initialize();