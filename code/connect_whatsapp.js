const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, Browsers, downloadMediaMessage } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const AUTH_DIR = path.join(__dirname, '..', 'scratch', 'auth_info_baileys');
const OCR_BIN = path.join(__dirname, 'src', 'ocr_bin');

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    
    const sock = makeWASocket({
        auth: state,
        browser: Browsers.macOS('Desktop'),
        syncFullHistory: false
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log('\n=================================================');
            console.log('📱 SCAN THIS QR CODE WITH YOUR WHATSAPP APP');
            console.log('=================================================\n');
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            console.log(`\nConnection closed (status code: ${statusCode}).`);

            if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
                console.log('Session expired or logged out. Clearing old session data...');
                if (fs.existsSync(AUTH_DIR)) {
                    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
                }
                setTimeout(connectToWhatsApp, 1000);
            } else {
                console.log('Attempting to reconnect in 3 seconds...');
                setTimeout(connectToWhatsApp, 3000);
            }
        } else if (connection === 'open') {
            console.log('\n=================================================');
            console.log('🎉 SUCCESSFULLY CONNECTED TO LIVE WHATSAPP!');
            console.log('Send any message to your WhatsApp from another phone to test AI routing.');
            console.log('=================================================\n');
        }
    });

    sock.ev.on('messages.upsert', async (m) => {
        const msg = m.messages[0];
        if (!msg || !msg.message || msg.key.fromMe) return;
        if (msg.key.remoteJid === 'status@broadcast') return; // Skip WhatsApp status broadcasts

        // Extract text across all WhatsApp message types
        const messageContent = msg.message;
        let text = 
            messageContent.conversation ||
            messageContent.extendedTextMessage?.text ||
            messageContent.imageMessage?.caption ||
            messageContent.videoMessage?.caption ||
            messageContent.documentMessage?.caption ||
            (messageContent.audioMessage ? '[Voice Note Audio]' : '') ||
            (messageContent.stickerMessage ? '[Sticker]' : '') ||
            '';

        let mediaType = '';
        let ocrText = '';

        if (messageContent.imageMessage) {
            mediaType = 'image';
            try {
                const buffer = await downloadMediaMessage(msg, 'buffer', {});
                const tmpPath = path.join(__dirname, '..', 'scratch', 'temp_incoming_image.png');
                fs.writeFileSync(tmpPath, buffer);
                
                if (fs.existsSync(OCR_BIN)) {
                    ocrText = execSync(`"${OCR_BIN}" "${tmpPath}"`, { encoding: 'utf-8' }).trim();
                    if (ocrText) {
                        console.log(`🖼️  Extracted OCR Text from Incoming Image Poster:\n   "${ocrText}"`);
                        text = (text + ' ' + ocrText).trim();
                    }
                }
            } catch (err) {
                console.log('Media download / OCR warning:', err.message);
            }
        }

        text = text.trim();
        if (!text) return; // Skip empty background protocol syncs

        const sender = msg.key.remoteJid;
        const pushName = msg.pushName || 'Sender';
        const isGroup = sender.endsWith('@g.us');

        try {
            // Forward payload to Python Router Webhook Server
            const res = await axios.post('http://localhost:8080/webhook/whatsapp', {
                message_id: msg.key.id,
                user_id: 'me',
                conversation_type: isGroup ? 'group' : 'personal',
                sender_user_id: sender,
                message_text: text,
                created_at: new Date().toISOString()
            });

            const decision = res.data;
            const action = (decision.action || 'digest').toLowerCase();
            
            // ANSI styling tokens
            const RESET = "\x1b[0m";
            const BOLD = "\x1b[1m";
            const DIM = "\x1b[2m";
            const GREEN = "\x1b[92m";
            const YELLOW = "\x1b[93m";
            const RED = "\x1b[91m";
            const CYAN = "\x1b[96m";
            const MAGENTA = "\x1b[95m";

            let actionBadge = `${YELLOW}📥 DIGEST (Batch Later)${RESET}`;
            if (action === 'notify') actionBadge = `${GREEN}🔔 NOTIFY (Interrupt Now)${RESET}`;
            if (action === 'mute')   actionBadge = `${RED}🔕 MUTE   (Suppress Risk)${RESET}`;

            const confVal = parseFloat(decision.confidence) || 0.8;
            const bars = '█'.repeat(Math.round(confVal * 10)) + '░'.repeat(10 - Math.round(confVal * 10));

            console.log(`\n${BOLD}┌── 📩 Incoming WhatsApp Message ───────────────────────────────────────────────┐${RESET}`);
            console.log(`│  ${BOLD}Sender${RESET}   : ${pushName} (${sender})`);
            console.log(`│  ${BOLD}Type${RESET}     : ${MAGENTA}${isGroup ? 'GROUP CHAT' : 'PERSONAL CHAT'}${RESET}`);
            console.log(`│  ${BOLD}Message${RESET}  : "${text.length > 75 ? text.substring(0, 72) + '...' : text}"`);
            console.log(`├── 🤖 AI Routing Decision ─────────────────────────────────────────────────────┤`);
            console.log(`│  ${BOLD}Decision${RESET} : ${BOLD}${actionBadge}`);
            console.log(`│  ${BOLD}Category${RESET} : ${CYAN}${BOLD}${decision.message_type?.toUpperCase()}${RESET}`);
            console.log(`│  ${BOLD}Score${RESET}    : [${bars}] ${(confVal * 100).toFixed(1)}%`);
            console.log(`│  ${BOLD}Rationale${RESET}: ${decision.reason}`);
            console.log(`│  ${BOLD}Evidence${RESET} : ${DIM}${decision.evidence_message_ids || 'none'}${RESET}`);
            console.log(`${BOLD}└───────────────────────────────────────────────────────────────────────────────┘${RESET}\n`);

        } catch (err) {
            console.error('\x1b[91m⚠️ Error forwarding message to AI router (ensure python3 code/server.py 8080 is running):\x1b[0m', err.message);
        }
    });
}

connectToWhatsApp();
