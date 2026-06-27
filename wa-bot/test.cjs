const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: false,
        args: ['--no-sandbox']
    }
});

client.on('qr', (qr) => {
    qrcode.generate(qr, { small: true });
    console.log('Scan QR');
});

client.on('ready', () => {
    console.log('WhatsApp Ready!');
});

client.on('auth_failure', msg => {
    console.log('Auth Failure:', msg);
});

client.initialize();