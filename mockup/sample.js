// Sample data for the hosted preview. Used only when the Lifeline API cannot be reached at all, as on a Netlify link
// where no API runs, so teammates see every screen filled in. Every sample is labelled "Sample" on screen and moves
// nothing. The figures follow the demo fixtures: fixtures/demo_user.yaml and rails/fake_router.py (fees there are
// fixtures too, not published fees). The live demo, with the real API, never uses this file.

const now = Date.now();
const iso = (hoursAgo) => new Date(now - hoursAgo * 3600e3).toISOString();
const ahead = (days) => new Date(now + days * 86400e3).toISOString();

const LEDGER = [
  { seq: 1, ts: iso(70), kind: "receipt", payload: { receipt: { receipt_id: "sim_pix-0001", rail: "sim_pix", amount: "1200", currency: "SGD", status: "completed", simulated: true } } },
  { seq: 2, ts: iso(50), kind: "decision", payload: { decision: { allowed: false, rule_ids: ["R01"] }, action: { type: "transfer" } } },
  { seq: 3, ts: iso(26), kind: "note", payload: { kind: "rescue_started" } },
  { seq: 4, ts: iso(25.9), kind: "execution", payload: { result: { freeze: { status: "done" } } } },
  { seq: 5, ts: iso(25.8), kind: "receipt", payload: { receipt: { receipt_id: "wise-0001", rail: "wise", amount: "300", currency: "SGD", status: "completed", simulated: true } } },
  { seq: 6, ts: iso(25.7), kind: "note", payload: { kind: "family_notice" } },
].map((e) => ({ ...e, actor: "agent", hash: "sample" + String(e.seq).padStart(58, "0"), prev_hash: "" }));

const ROUTES = [
  { rail: "wise", fee: "5.60", spread_cost: "0", currency_from: "SGD", arrival_hours: 24, simulated: false },
  { rail: "sim_pix", fee: "0", spread_cost: "0", currency_from: "SGD", arrival_hours: 0, simulated: true },
  { rail: "bank_wire", fee: "25", spread_cost: "30", currency_from: "SGD", arrival_hours: 72, simulated: false },
];

// The sample replies in the three languages, so the preview follows the language picker.
const SAY = {
  en: { scam: "This looks like a scam: real banks don't ask you to move money to a 'safe account' by message. Don't reply to it, and check in your bank's own app.",
    blocked: "Your pasted text asked Lifeline to make a payment. Lifeline did not do that, because only your own words can start an action.",
    rent: "Here's your rent payment to check before anything moves.", balance: "You have 2,300 SGD and 150 BRL.",
    parents: "Your parents' transfer from China is with the bank and under review. Banks often check documents at this stage. Nothing for you to do yet; ignore anyone asking you to pay a fee to release it.",
    other: "In the live demo, Lifeline's AI answers here. This preview shows sample replies: try Pay rent, My balance, or attach a message and ask if it's a scam.",
    sent: "Done. 1,200 SGD was sent over wise. Receipt wise-0002.", none: "This turn: nothing was proposed, changed or sent.", step: "This turn: a sample step; nothing was sent.",
    r1: "Lifeline started a rescue. First answer the question you set before you left: What are the last four characters of your student pass number?", r2: "That answer matches your plan. Which card is it?", r3: "Freeze this card now? Payments on it stop until you unfreeze it.",
    r4: "Your card is frozen. From now on use your backup card, the Revolut card. Do you need emergency money? 300 SGD can go to your own Singapore account.", r5: "Done. Your Wise card is frozen, payments moved to your Revolut card, and your family has been told." },
  pt: { scam: "Isto parece golpe: bancos de verdade não pedem para mover dinheiro para uma \"conta segura\" por mensagem. Não responda e confira no app do seu banco.",
    blocked: "O texto colado pediu ao Lifeline um pagamento. O Lifeline não fez isso, porque só suas palavras podem iniciar uma ação.",
    rent: "Aqui está o pagamento do aluguel para conferir antes de qualquer coisa se mover.", balance: "Você tem 2.300 SGD e 150 BRL.",
    parents: "A transferência dos seus pais da China está no banco, em análise. Bancos costumam conferir documentos nesta etapa. Você não precisa fazer nada; ignore quem pedir taxa para liberar.",
    other: "Na demo ao vivo, a IA do Lifeline responde aqui. Esta prévia mostra respostas de exemplo: tente Pagar aluguel, Meu saldo, ou anexe uma mensagem e pergunte se é golpe.",
    sent: "Pronto. 1.200 SGD foram enviados via wise. Recibo wise-0002.", none: "Neste turno: nada foi proposto, alterado ou enviado.", step: "Neste turno: uma etapa de exemplo; nada foi enviado.",
    r1: "O Lifeline iniciou um resgate. Primeiro responda à pergunta que você definiu antes de viajar: quais são os quatro últimos caracteres do seu cartão de estudante?", r2: "A resposta confere com seu plano. Qual cartão é?", r3: "Bloquear este cartão agora? Os pagamentos nele param até você desbloquear.",
    r4: "Seu cartão está bloqueado. A partir de agora use o cartão reserva, o Revolut. Precisa de dinheiro de emergência? 300 SGD podem ir para sua conta em Singapura.", r5: "Pronto. Seu cartão Wise está bloqueado, os pagamentos foram para o Revolut e sua família foi avisada." },
  zh: { scam: "这看起来是诈骗：真正的银行不会通过消息让您把钱转到「安全账户」。请不要回复，并在您银行的官方应用中核实。",
    blocked: "您粘贴的文字要求 Lifeline 付一笔款，Lifeline 没有这样做，因为只有您自己的话才能发起操作。",
    rent: "这是您的房租付款，请在转出前核对。", balance: "您有 2,300 SGD 和 150 BRL。",
    parents: "您父母从中国汇来的钱正在银行审核中。银行在这一步常会核对材料。您暂时无需操作；如有人要求支付「解冻费」，请不要理会。",
    other: "在实时演示中，这里由 Lifeline 的 AI 回答。此预览显示示例回复：试试「交房租」「我的余额」，或附上一条消息问是否诈骗。",
    sent: "完成。1,200 SGD 已经由 wise 发出。回执 wise-0002。", none: "本轮：未提出、更改或发送任何内容。", step: "本轮：示例步骤，未发送任何内容。",
    r1: "Lifeline 已启动救援。请先回答您出发前设置的问题：您学生证号码的最后四位是什么？", r2: "答案与您的计划相符。是哪张卡？", r3: "现在冻结这张卡吗？冻结后此卡的付款会停止，直到您解冻。",
    r4: "您的卡已冻结。之后请使用备用卡 Revolut。需要应急资金吗？可以转 300 SGD 到您自己的新加坡账户。", r5: "完成。您的 Wise 卡已冻结，付款改用 Revolut 卡，并已通知您的家人。" },
};
const say = (body, key) => (SAY[body?.lang] || SAY.en)[key];

const done = (body, text, extra = {}) => ({ text, blocked: [], turn_summary: say(body, "none"), sample: true, ...extra });

function chat(body) {
  const t = (body.text || "").toLowerCase();
  if (body.pasted_text) return done(body, say(body, "scam"), { blocked: [say(body, "blocked")] });
  if (/rent|landlord|aluguel|locador|房租|房东/.test(t)) {
    return { text: say(body, "rent"), blocked: [], sample: true,
      turn_summary: "This turn: a transfer of 1200 SGD to landlord_sp: proposed, waiting for your confirmation.",
      confirmation: { confirmation_token: "sample", warning_key: "warn.transfer.irreversible", expires_in_seconds: 300,
        action: { type: "transfer", amount: "1200", currency: "SGD", payee_id: "landlord_sp", purpose: "rent" },
        routes: ROUTES, selected_route: ROUTES[0] } };
  }
  if (/balance|saldo|余额/.test(t)) return done(body, say(body, "balance"));
  if (/parent|arrived|where|pais|chegou|父母|到账/.test(t)) return done(body, say(body, "parents"));
  return done(body, say(body, "other"));
}

let rescueStep = 0;
let rescueLang = "en";
function rescue(path, body) {
  if (body?.lang) rescueLang = body.lang;
  const b = { lang: rescueLang };
  if (path.endsWith("/start")) { rescueStep = 1; return r(say(b, "r1"), "S1", "answer_identity_question"); }
  if (rescueStep === 1) { rescueStep = 2; return r(say(b, "r2"), "S2", "choose_card", { card_names: ["Wise debit card", "Revolut card"] }); }
  if (rescueStep === 2) { rescueStep = 3; return r(say(b, "r3"), "S2", "confirm_freeze", {}, { confirmation: { confirmation_token: "sample" } }); }
  if (rescueStep === 3) { rescueStep = 4; return r(say(b, "r4"), "S5", "confirm_transfer_or_skip", { live_instrument: "revolut:card_02" }, { confirmation: { confirmation_token: "sample" } }); }
  rescueStep = 0;
  return r(say(b, "r5"), "done", "done");
}
function r(text, state, doNow, rescueExtra = {}, extra = {}) {
  return { text, blocked: [], sample: true, turn_summary: say({ lang: rescueLang }, "step"), ...extra,
    rescue: { state_after: state, do_now: doNow, card_names: [], live_instrument: null, issuer_link: null, ...rescueExtra } };
}

export function sample(method, path, body = {}) {
  if (path.startsWith("/reminders/")) return { due: [], upcoming: [{ text: "Rent is due", due: ahead(5) }, { text: "Renew the student pass", due: ahead(20) }] };
  if (path.endsWith("/verify")) return { first_broken_seq: null };
  if (path.startsWith("/ledger/")) return LEDGER;
  if (path === "/chat") return chat(body);
  if (path === "/confirm") return { text: say(body, "sent"), blocked: [], sample: true,
    turn_summary: say(body, "step"),
    receipt: { receipt_id: "wise-0002", rail: "wise", amount: "1200", currency: "SGD", status: "completed", simulated: true } };
  if (path.startsWith("/rescue/")) return rescue(path, body);
  return null;
}
