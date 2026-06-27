const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const axios = require("axios");

const API_URL = "http://127.0.0.1:8001/agent/whatsapp-web"; 

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

    // Skip groups, broadcasts, and newsletters
    if (
      senderId.includes("@g.us") ||
      senderId.includes("status@broadcast") ||
      senderId.includes("@newsletter")
    ) {
      return;
    }

    // FIX 1: Opt-in to tracking if it's an explicit command OR if they upload media/car images
    if (lowerText === "reset" || lowerText === "get my car" || msg.hasMedia) {
      activeUsers.add(senderId);
    }

    // Safety Gate: Drops unrelated personal conversations
    if (!activeUsers.has(senderId)) {
      return;
    }

    console.log("MESSAGE RECEIVED:", senderId, text);

    let mediaBase64 = null;
    let mimeType = null;

    // FIX 2: Added console reporting steps for raw media download debugging
    if (msg.hasMedia) {
      console.log("📸 Media message detected. Downloading raw data asset...");
      try {
        const media = await msg.downloadMedia();
        if (media && media.data) {
          mediaBase64 = media.data;
          mimeType = media.mimetype;
          console.log(`✅ Extracted base64 string successfully (${mediaBase64.length} chars).`);
        } else {
          console.error("❌ Media stream resolved empty data payload.");
        }
      } catch (mediaErr) {
        console.error("❌ Failed while downloading media asset stream:", mediaErr.message);
      }
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
      { timeout: 180000 }
    );

    console.log("FASTAPI RESPONSE:", response.data);

    // 1. Reply directly back to the message sender
    if (response.data.reply) {
      try {
        let targetSender = senderId;
        if (!targetSender.includes("@")) {
          targetSender = targetSender + "@c.us";
        }
        console.log(`Sending message to: ${targetSender}`);
        await client.sendMessage(targetSender, response.data.reply);
        console.log("🚀 Message successfully delivered!");
      } catch (sendError) {
        console.error("❌ Failed to send WhatsApp reply message:", sendError.message);
      }
    }

    // 2. Dispatch Target 1 (Customer notifications)
    if (response.data.sendTo && response.data.message) {
      let target = response.data.sendTo;
      if (!target.includes("@")) target = target + "@c.us";
      await client.sendMessage(target, response.data.message);
      console.log(`🚀 Forwarded message sent to Target: ${target}`);
    }

    // 3. Dispatch Target 2 (Driver notifications)
    if (response.data.driverTo && response.data.driverMessage) {
      let driverTarget = response.data.driverTo;
      if (!driverTarget.includes("@")) driverTarget = driverTarget + "@c.us";
      await client.sendMessage(driverTarget, response.data.driverMessage);
      console.log(`🚀 Forwarded message sent to Driver Target: ${driverTarget}`);
    }

    // FIX 3: REMOVED "reset" from clearing state immediately! Only clear memory once session hits "paid".
    if (lowerText === "paid") {
       activeUsers.delete(senderId);
       console.log(`🧹 Session complete. Removed ${senderId} from memory stack.`);
    }

  } catch (err) {
    console.error("BOT ERROR:", err.message);
  }
});

client.initialize();