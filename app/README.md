# Lifeline app

This folder is the frontend of lane C. It is plain HTML, CSS and JavaScript with no build step, and it talks only to the Lifeline API that `make dev` starts, as `docs/api.md` describes. It is built for a phone screen first and works in English, Portuguese and Chinese.

## Running it

Two terminals, both in the repository folder.

In the first, start the API as the main README says:

```bash
make dev
```

In the second, serve the app:

```bash
cd app
npm start
```

Then open `http://127.0.0.1:3000` in a browser. The app calls the API on `http://127.0.0.1:8000`. To point it at the API on another port of this machine, add `?api=http://127.0.0.1:PORT` to the address; any address that is not on this machine is ignored.

The chat needs a model key in `.env`, as `.env.example` lists. Without one the chat says plainly that Lifeline's AI is not available and that nothing was done. The rescue and the ledger need no key.

## What it has

1. A language picker. Its list, each language's own name and its writing direction come only from `GET /health`. The page's `lang` and `dir` follow the choice, so a right to left language would turn the layout. The app's own labels exist in English, Portuguese and Chinese and fall back to English for any other language.
2. A chat screen with a separate paste box. What the student types goes in `text` and what they paste goes in `pasted_text`, and the two are never joined. A paste or a drop into the message box is moved to the paste box. A paste with no typed words is never sent.
3. A confirmation card built from the reply's `confirmation` field: the warning, the action, every route with the selected one marked, and the council's advice when present. The council's runner up is shown only when its disagreement score is above 0.4, the backend's `RUNNER_UP_DISAGREEMENT`, as the reply text does, and the reasons it was asked are shown as short labels in the chosen language; an id the app does not know is left off. A route is marked Blocked only when it has a blocked reason, its limit is not ok, or its status is down; a degraded route is still offered by the loop, so it is not marked. The token is kept only in memory, inside the card, and is sent back to `/confirm` exactly as it came, once. A token the server does not accept, because it expired, was used or was never issued, comes back as a normal reply that says nothing was sent, and the app shows it as one.
4. The two sentences code writes in every reply, shown on their own lines: each blocked request sentence at the top, and the sentence that begins `This turn:`, `Neste turno:` or `本轮：` at the bottom. The app reads them from the reply's `blocked` and `turn_summary` fields. Only when a field is absent, as from a server older than those fields, does it find that sentence by its wording.
5. The lost card rescue, driven only by `rescue.do_now`, for all seven values. Its fields take typed words only: pasting and dropping are refused. An empty identity answer is never sent, because the server would count it as a wrong one, and the answer is cleared as soon as it is sent.
6. The ledger: every entry, newest first, with the result of verify above it: whether the chain is intact and the first broken entry, the anchor status, the integrity hold, and whether demo keys are signing.
7. A welcome screen, shown on opening before the tabs: the logo, one sentence on what Lifeline is for, three short cards to swipe or tap through, on what Lifeline does, what it never does and how it works, and one button, Continue as the demo student, with a line saying the demo runs as one demo student with demo limits, no real money moves and sign in is not built. It has no password field and no account. Continue opens Chat, and the Welcome button in the top bar brings it back. Nothing remembers a visit, so it shows on every opening. `?welcome=off` in the address skips it; the browser tests use that.
8. The Guide tab, after Ledger: six sections for the moments a student meets, paying rent abroad, a message about money, a lost card, money from or to China, money from India or to Brazil, and reading the ledger, then How Lifeline protects you in six sections. Example sentences can be tapped to put their words in the message box, never in the paste box. When the tab is shown it reads `GET /ledger/{user_id}/verify` once and shows the result, with a line when development keys are signing. Its sentences are in `src/guide-content.js` and `src/i18n.js`.
9. The logo, an original mark drawn in `src/logo.js`: one continuous line with a single heartbeat pulse, in the accent colour, beside the wordmark Lifeline. It is in the top bar, on the welcome screen, and in `index.html` as the favicon, drawn from the same path.

A banner in the header says the app is a demo and that no real money moves on any route, in the chosen language. It stays on screen on every tab, and shows in English even before `/health` answers.

The model's words in a reply are read as basic markdown: bold with two asterisks, italic with one, bullet and numbered lists, pipe tables with a separator row of dashes, paragraphs and line breaks. A wide table scrolls sideways inside the reply, never the whole page. Underscores are never markup, so ids such as landlord_sp stay whole. The two sentences code writes, and everything else the server sends, are shown as plain text.

The app never uses browser storage, and it never puts text from the server into the page as HTML.

## Tests

The tests need the repository's `.venv`, made by the quick start in the main README, and Node 22.

```bash
cd app
npm install
npm test
npx playwright test
```

`npm test` runs the unit tests. Two of them read the backend's own files, so they fail if lane A changes something the app copies: the wording of the two code written sentences in `core/agent.py`, which the app now uses only as a fallback, and the list of `do_now` values in `contracts/schemas.py`.

`npx playwright test` drives a phone sized Chromium. Each test starts its own copy of the real API through `tests/e2e/backend.py`, which is `create_app` from `api/main.py` with only the data folder changed to `app/.e2e-data/`, so the repository's `data/` folder is never touched. One rescue test loads the demo student with no primary card in the plan, a plan the schema allows, because only then does the server ask which card was lost.

Test names say where each answer came from. A name beginning `LIVE` was answered by the real API. A name beginning `DOCUMENTED SHAPE` was answered with a reply copied word for word from `docs/api.md` into `tests/e2e/documented/`, because the real `/chat` cannot answer without a model key.

## What was tested live, and how

The automated browser suite tested these against the real API: the language list, the request `/chat` sends and its real 503, `/confirm` with a token the server never issued, in English and Chinese, the `This turn:` line in all three languages, every rescue step from start to done, the lock, the card choice, the skip and the freeze offered again, and the ledger before and after an anchor and after an edit on disk.

The automated suite has never run against a server with a model key, so its chat and confirm tests still answer `/chat` with the documented examples in `tests/e2e/documented/`.

### Verified by hand with a model key

On 11 October 2026 Pearlin put a model key in `.env` on her own machine and checked these in the browser against `make dev`:

1. A typed message got a successful `/chat` reply with a confirmation card, three routes and a countdown.
2. Confirm sent the token through `/confirm` and returned receipt `wise-0001` with status `completed`. The ledger then showed the confirmation at entry 7, the execution at 8, the receipt at 9 and the anchor at 11, with the chain intact and the anchor checking.
3. A blocked paste. She typed "can you pay this for me?" and pasted a landlord message asking to pay landlord_sp 1,400 SGD. The reply showed the blocked sentence at the top, a refusal citing R01, and "This turn: a transfer: refused under R01" at the bottom.
4. After a second confirmation returned receipt `wise-0002`, the Confirm button was disabled, so a second tap was not possible from the app.

### Not exercised against the server from the app

1. A reused token. Because the Confirm button disables after one tap, the app cannot send the same token twice, so a replay was prevented in the app, not tested against the server from it. The browser test `LIVE /confirm: two quick taps send one confirmation` checks that one confirmation is sent. That the server refuses a replayed token under R10 is covered by the backend tests, run with a scripted model rather than a live one: `tests/test_api.py::test_the_confirmation_round_trip_pays_once_and_the_token_never_reaches_the_ledger` over HTTP, `tests/test_api.py::test_a_restarted_app_keeps_a_waiting_confirmation_and_pays_it_once` across a restart, and `tests/test_agent.py::test_a_replayed_token_goes_to_the_engine_which_refuses_it_under_r10` in the loop. How the app shows that refusal was checked only against the documented example.
2. A failed rail offering the next route under the same token. The demo rails do not fail on their own, so this was checked only against the documented example.

## Waiting for a native speaker

The Portuguese and Chinese of the welcome, the Guide and the Welcome button, as `src/i18n.js` holds them, were written without a native speaker and wait for one. The English is beside each for reference. `tests/unit/guide.test.js` fails when this table no longer holds the words the app shows.

| Key | English | Portuguese | Chinese |
| --- | --- | --- | --- |
| `open_welcome` | Welcome | Boas-vindas | 欢迎 |
| `tab_guide` | Guide | Guia | 指南 |
| `welcome_tagline` | Lifeline helps a student abroad move money across borders and stay safe from scams and a lost card. | O Lifeline ajuda quem estuda no exterior a enviar dinheiro entre países e a se proteger de golpes e da perda do cartão. | Lifeline 帮助在海外求学的学生跨境转账，并防范诈骗和丢卡带来的麻烦。 |
| `welcome_next` | Next | Próximo | 下一张 |
| `welcome_card_n` | Card {n} of 3 | Cartão {n} de 3 | 第 {n} 张，共 3 张 |
| `welcome_continue` | Continue as the demo student | Continuar como o estudante de demonstração | 以演示学生身份继续 |
| `welcome_demo_note` | This demo runs as one demo student with demo limits, and no real money moves; sign in is not built, as the security self assessment says. | Esta demonstração funciona como um único estudante de demonstração, com limites de demonstração, e nenhum dinheiro real se move; o login não foi construído, como diz a autoavaliação de segurança. | 本演示以一名演示学生和演示限额运行，不会转移真实资金；登录功能尚未构建，安全自评报告中也这样写明。 |
| `guide_intro` | Answers for the moment you are in. Tap an example to put its words in your message box. | Respostas para o momento em que você está. Toque em um exemplo para colocar as palavras na caixa de mensagem. | 针对您此刻的问题给出答案。点按示例，就会把这些话放进消息框。 |
| `guide_try` | Tap to use these words: | Toque para usar estas palavras: | 点按使用这些话： |
| `guide_protect_title` | How Lifeline protects you | Como o Lifeline protege você | Lifeline 如何保护您 |
| `guide_verify_title` | Your ledger right now | O seu registro agora | 您的账本现状 |
| `welcome_does_title` | What Lifeline does | O que o Lifeline faz | Lifeline 做什么 |
| `welcome_does_1` | It moves your money across borders, within limits you set. | Envia seu dinheiro entre países, dentro dos limites que você define. | 在您设定的限额内，帮您跨境转账。 |
| `welcome_does_2` | It protects you from scams and walks you through a lost card. | Protege você de golpes e guia você quando perde o cartão. | 帮您防范诈骗，丢卡时一步步带您处理。 |
| `welcome_never_title` | What it never does | O que ele nunca faz | 它从不做什么 |
| `welcome_never_1` | It never holds your money. | Nunca guarda o seu dinheiro. | 从不保管您的钱。 |
| `welcome_never_2` | It never gives investment advice. | Nunca dá conselhos de investimento. | 从不提供投资建议。 |
| `welcome_never_3` | It never changes your limits in chat. | Nunca muda os seus limites pelo chat. | 从不在对话中更改您的限额。 |
| `welcome_never_4` | It never asks for your identity documents. | Nunca pede os seus documentos de identidade. | 从不索要您的身份证件。 |
| `welcome_how_title` | How it works | Como funciona | 它如何运作 |
| `welcome_how_1` | You ask in your own words. | Você pede com as suas próprias palavras. | 您用自己的话提出请求。 |
| `welcome_how_2` | Nothing moves until you confirm. | Nada se move até você confirmar. | 您确认之前，什么都不会转出。 |
| `welcome_how_3` | Every step is recorded where you can see it, on the Ledger tab. | Cada passo fica registrado onde você pode ver, na aba Registro. | 每一步都记录在您能看到的地方，就在账本标签页。 |
| `guide_rent_title` | Paying rent abroad | Pagar o aluguel no exterior | 在海外付房租 |
| `guide_rent_1` | Type what you need in your own words, like the example below. | Escreva o que você precisa com as suas próprias palavras, como no exemplo abaixo. | 用您自己的话写下需要做什么，就像下面的示例。 |
| `guide_rent_2` | Lifeline answers with a confirmation card: what will be sent, to whom, and the routes it compared, each with its fee and time. A route goes through a provider, which Lifeline calls a rail, and the one it picked is marked Selected. | O Lifeline responde com um cartão de confirmação: o que será enviado, para quem, e as rotas que comparou, cada uma com a tarifa e o prazo. Uma rota passa por um provedor, que o Lifeline chama de trilho, e a escolhida aparece como Selecionada. | Lifeline 会回复一张确认卡：要转出什么、转给谁，以及它比较过的各条路线，每条都有费用和时间。路线经由一个服务商，Lifeline 称之为通道，被选中的那条标为已选。 |
| `guide_rent_3` | A route marked Simulated copies a real rail's rules, and the others are fixtures, stand ins with demo fees; on this demo no route moves real money, as the banner says. | Uma rota marcada como Simulada copia as regras de um trilho real, e as outras são fixtures, substitutas com tarifas de demonstração; nesta demonstração nenhuma rota move dinheiro real, como diz o aviso. | 标为模拟的路线照搬真实通道的规则，其余的是固定样例，即带演示费用的替代品；正如横幅所说，在本演示中没有任何路线会转移真实资金。 |
| `guide_rent_4` | The card holds a one time code, called a token, for this exact payment. Tap Confirm within five minutes; after that the token expires and nothing is sent. | O cartão guarda um código de uso único, chamado token, para este pagamento exato. Toque em Confirmar em até cinco minutos; depois disso o token expira e nada é enviado. | 确认卡带有一个一次性代码，称为令牌，只对应这一笔付款。请在五分钟内点按确认；之后令牌过期，什么都不会转出。 |
| `guide_ex_rent` | Send this month's rent of 1,200 SGD to my landlord in Brazil | Envie o aluguel deste mês, de 1.200 SGD, para o meu senhorio no Brasil | 把这个月 1,200 新元的房租转给我在巴西的房东 |
| `guide_message_title` | Someone sent me a message about money | Alguém me mandou uma mensagem sobre dinheiro | 有人给我发了关于钱的消息 |
| `guide_message_1` | Put the message in the Pasted text box under your message, and type your own question in the message box. If you paste into the message box, the app moves it to the Pasted text box. | Coloque a mensagem na caixa Texto colado, abaixo da sua mensagem, e escreva a sua própria pergunta na caixa de mensagem. Se você colar na caixa de mensagem, o app move o texto para a caixa Texto colado. | 把那条消息放进您消息下方的“粘贴的文字”框，在消息框里写下您自己的问题。如果您粘贴到消息框，应用会把它移到“粘贴的文字”框。 |
| `guide_message_2` | Pasted text can never start a payment, even when it asks for one, because only your own words can. | Um texto colado nunca pode iniciar um pagamento, mesmo quando pede um, porque só as suas próprias palavras podem. | 粘贴的文字永远不能发起付款，即使它要求付款，因为只有您自己的话才可以。 |
| `guide_message_3` | When it asks Lifeline to act, the reply starts with a Blocked line that says what it asked for and that nothing was done. | Quando ele pede ao Lifeline para agir, a resposta começa com uma linha Bloqueado que diz o que foi pedido e que nada foi feito. | 如果它要求 Lifeline 执行操作，回复开头会有一行“已拦截”，说明它要求了什么，并说明什么都没有做。 |
| `guide_ex_message` | Is this message a scam? | Esta mensagem é um golpe? | 这条消息是诈骗吗？ |
| `guide_card_title` | I lost my card | Perdi o meu cartão | 我的卡丢了 |
| `guide_card_1` | Open the Lost card tab, choose lost or stolen, and say what happened in your own words. | Abra a aba Cartão perdido, escolha perdido ou roubado e conte o que aconteceu com as suas próprias palavras. | 打开卡丢失标签页，选择丢失或被盗，用您自己的话说明发生了什么。 |
| `guide_card_2` | Lifeline first asks the question in your rescue plan; three wrong answers lock the rescue. | Primeiro o Lifeline faz a pergunta do seu plano de resgate; três respostas erradas bloqueiam o resgate. | Lifeline 先问您救援计划里的问题；答错三次，救援就会锁定。 |
| `guide_card_3` | Then it offers to freeze the card, which you confirm, or gives you a link to the card issuer when it cannot freeze it, and it moves your payments to your backup card when your plan allows it. | Depois ele oferece bloquear o cartão, o que você confirma, ou dá um link para o emissor do cartão quando não consegue bloqueá-lo, e passa os seus pagamentos para o cartão reserva quando o seu plano permite. | 然后它会提出冻结这张卡，由您确认；如果无法冻结，就给您发卡机构的链接；您的计划允许时，它会把付款转到您的备用卡。 |
| `guide_card_4` | If you need money now it offers an emergency transfer, which you confirm too, and it tells your family only when your plan says so. | Se você precisa de dinheiro agora, ele oferece uma transferência de emergência, que você também confirma, e avisa a sua família só quando o seu plano diz isso. | 如果您现在就需要钱，它会提出一笔紧急转账，同样由您确认；只有您的计划写明时，它才会通知您的家人。 |
| `guide_china_title` | Money from or to China | Dinheiro da China ou para a China | 来自中国或汇往中国的钱 |
| `guide_china_1` | Chinese bank cards have a yearly and a daily cap on cash taken out abroad. Tell Lifeline each withdrawal; it counts them and warns you before you reach the cap. | Cartões de bancos chineses têm um limite anual e um diário para saques em dinheiro no exterior. Conte ao Lifeline cada saque; ele soma os saques e avisa antes de você chegar ao limite. | 中国银行卡在境外提取现金有年度和每日上限。每次取现都告诉 Lifeline；它会累计，并在您接近上限前提醒您。 |
| `guide_china_2` | Each person in China has a yearly quota for buying foreign currency, and Lifeline refuses to spread a transfer over relatives' quotas. | Cada pessoa na China tem uma cota anual para comprar moeda estrangeira, e o Lifeline se recusa a dividir uma transferência entre as cotas de parentes. | 中国境内每人每年有购汇额度，Lifeline 会拒绝把一笔转账分摊到亲属的额度上。 |
| `guide_china_3` | Lifeline refuses a direct bank transfer from China to NUS for tuition, and tells you why, with its source. | O Lifeline recusa uma transferência bancária direta da China para a NUS para pagar a mensalidade, e diz por quê, com a fonte. | Lifeline 会拒绝从中国直接银行汇款到 NUS 缴学费，并告诉您原因和来源。 |
| `guide_ex_china_1` | My parents in China want to send my semester's costs to Singapore, what will the bank ask for and when should they start | Meus pais na China querem enviar os custos do meu semestre para Singapura, o que o banco vai pedir e quando eles devem começar | 我在中国的父母想把我这学期的费用汇到新加坡，银行会要求什么，他们应该什么时候开始 |
| `guide_ex_china_2` | Warn me before I reach the overseas cash withdrawal cap on my Chinese cards | Me avise antes de eu chegar ao limite de saque em dinheiro no exterior nos meus cartões chineses | 在我接近中国银行卡境外取现上限之前提醒我 |
| `guide_inbr_title` | Money from India, or to Brazil | Dinheiro da Índia, ou para o Brasil | 来自印度的钱，或汇往巴西的钱 |
| `guide_inbr_1` | A parent in India can send you money in Singapore through UPI to PayNow, only to support a relative abroad or as a gift, and under a daily cap. | Um pai ou uma mãe na Índia pode enviar dinheiro para você em Singapura pelo UPI para PayNow, só para sustentar um parente no exterior ou como presente, e abaixo de um limite diário. | 在印度的父母可以通过 UPI 到 PayNow 把钱汇给您在新加坡的账户，仅限赡养海外亲属或作为赠与，并且不超过每日上限。 |
| `guide_inbr_2` | Lifeline shows a route that breaks either rule as Blocked, with the reason and its source. | O Lifeline mostra uma rota que quebra qualquer uma dessas regras como Bloqueada, com o motivo e a fonte. | 违反其中任一规则的路线，Lifeline 会标为不可用，并给出原因和来源。 |
| `guide_inbr_3` | To Brazil, Pix pays only a payee whose Pix key is on file. A Pix key is the phone number, email or registration number a person in Brazil uses to receive Pix. | Para o Brasil, o Pix paga só um destinatário cuja chave Pix está registrada. A chave Pix é o celular, o e-mail ou o número de cadastro que uma pessoa no Brasil usa para receber Pix. | 汇往巴西时，Pix 只付给已登记 Pix 键的收款人。Pix 键是巴西人用来接收 Pix 的手机号、电子邮箱或登记号码。 |
| `guide_ledger_title` | Reading your ledger | Como ler o seu registro | 如何阅读您的账本 |
| `guide_ledger_1` | The Ledger tab lists every step Lifeline took, newest first. Each entry carries a hash, a fingerprint of its contents and of the entry before it. | A aba Registro lista cada passo do Lifeline, do mais novo ao mais antigo. Cada entrada leva um hash, uma impressão digital do seu conteúdo e da entrada anterior. | 账本标签页按从新到旧列出 Lifeline 的每一步。每条记录都带有一个哈希，即它的内容和上一条记录的指纹。 |
| `guide_ledger_2` | Intact means no entry was changed or removed since it was written. | Íntegro quer dizer que nenhuma entrada foi alterada ou removida depois de escrita. | 完好表示每条记录写入后都没有被更改或删除。 |
| `guide_ledger_3` | Anchored means the latest fingerprint was also saved outside the ledger, in a signed file or on a FISCO BCOS chain, a blockchain on this machine, so a later change would show. | Ancorado quer dizer que a última impressão digital também foi guardada fora do registro, num arquivo assinado ou numa cadeia FISCO BCOS, um blockchain nesta máquina, então uma mudança depois apareceria. | 已锚定表示最新的指纹也保存在账本之外，在一个签名文件里，或在本机上的 FISCO BCOS 区块链上，因此之后的任何更改都会显现。 |
| `guide_ledger_4` | The block number says where that fingerprint sits on the chain, and appears only when Lifeline uses one. | O número do bloco diz onde essa impressão digital está na cadeia, e só aparece quando o Lifeline usa uma. | 区块号说明这个指纹在链上的位置，只有 Lifeline 使用区块链时才会显示。 |
| `protect_decides_title` | What decides | O que decide | 由什么决定 |
| `protect_decides_1` | The model proposes. The engine decides. A rail executes. The ledger records. | O modelo propõe. O motor decide. Um trilho executa. O registro anota. | 模型提议。引擎决定。通道执行。账本记录。 |
| `protect_decides_2` | Every action passes a plain Python engine with fourteen rules before anything happens, and no model is ever asked whether an action is allowed. | Cada ação passa por um motor simples em Python com catorze regras antes de qualquer coisa acontecer, e nenhum modelo é perguntado se uma ação é permitida. | 每个操作在发生之前都要经过一个有十四条规则的普通 Python 引擎，从不询问任何模型某个操作是否被允许。 |
| `protect_confirm_title` | What you confirm | O que você confirma | 您要确认什么 |
| `protect_confirm_1` | A payment, a new payee, a card freeze, setting up a standing payment and a cancellation run only after you confirm a token bound to that exact action, which expires in five minutes and can be used once. | Um pagamento, um novo destinatário, o bloqueio de um cartão, a criação de um pagamento recorrente e um cancelamento só acontecem depois que você confirma um token ligado àquela ação exata, que expira em cinco minutos e só pode ser usado uma vez. | 付款、新收款人、冻结卡、设立定期付款和取消，都只在您确认一个与该操作完全绑定的令牌之后才会执行；令牌五分钟后过期，只能使用一次。 |
| `protect_confirm_2` | After that, a standing payment's runs go ahead on their own, only within the pattern you confirmed. | Depois disso, as execuções de um pagamento recorrente seguem sozinhas, só dentro do padrão que você confirmou. | 之后，定期付款的每次执行会自动进行，但只限于您确认过的模式之内。 |
| `protect_never_title` | What can never start an action | O que nunca pode iniciar uma ação | 什么永远不能发起操作 |
| `protect_never_1` | Anything you paste, anything a provider sends back. | Qualquer coisa que você cola, qualquer coisa que um provedor devolve. | 您粘贴的任何内容，服务商返回的任何内容。 |
| `protect_never_2` | Lifeline reads it as information, refuses an action that comes only from it, and tells you at the top of the reply. | O Lifeline lê isso como informação, recusa uma ação que venha só daí e avisa você no topo da resposta. | Lifeline 把它当作信息来读，拒绝仅由它发起的操作，并在回复开头告诉您。 |
| `protect_recorded_title` | What is recorded | O que fica registrado | 记录了什么 |
| `protect_recorded_1` | Every proposal, decision, confirmation, execution and receipt is an entry in a hash chained ledger. | Cada proposta, decisão, confirmação, execução e recibo é uma entrada num registro encadeado por hash. | 每一次提议、决定、确认、执行和回执，都是哈希链账本中的一条记录。 |
| `protect_recorded_2` | Its head is anchored in a signed file, or on a FISCO BCOS chain when Lifeline is set to use one, and a ledger that fails verification stops every payment until it is clean. | O topo dele é ancorado num arquivo assinado, ou numa cadeia FISCO BCOS quando o Lifeline está configurado para usar uma, e um registro que falha na verificação para todos os pagamentos até ficar íntegro. | 账本的最新哈希锚定在一个签名文件中，或在 Lifeline 设置为使用 FISCO BCOS 链时锚定在链上；账本未通过验证时，所有付款都会停止，直到它恢复完整。 |
| `protect_recorded_3` | You can open every entry on the Ledger tab. | Você pode abrir cada entrada na aba Registro. | 您可以在账本标签页打开每一条记录。 |
| `protect_not_title` | What Lifeline does not do | O que o Lifeline não faz | Lifeline 不做什么 |
| `protect_not_1` | It holds no money and is not a licensed payment institution. It gives no investment advice. It never changes your limits in chat. It never asks for your identity documents. | Não guarda dinheiro e não é uma instituição de pagamento licenciada. Não dá conselhos de investimento. Nunca muda os seus limites pelo chat. Nunca pede os seus documentos de identidade. | 它不保管资金，也不是持牌支付机构。它不提供投资建议。它从不在对话中更改您的限额。它从不索要您的身份证件。 |
| `protect_demo_title` | What this demo is | O que é esta demonstração | 这个演示是什么 |
| `protect_demo_1` | Every rail here is a fixture or a simulation and no real money moves. The API runs on this machine only, with no sign in, for one demo student. | Cada trilho aqui é uma fixture ou uma simulação e nenhum dinheiro real se move. A API roda só nesta máquina, sem login, para um único estudante de demonstração. | 这里的每个通道都是固定样例或模拟，不会转移真实资金。API 只在本机运行，没有登录，只服务一名演示学生。 |
| `protect_demo_2` | The full security self assessment and the known limitations are in docs/self_assessment.md in the repository. | A autoavaliação de segurança completa e as limitações conhecidas estão em docs/self_assessment.md no repositório. | 完整的安全自评报告和已知局限，见代码仓库中的 docs/self_assessment.md。 |

## Known gaps

1. The Portuguese and Chinese labels were written without a native speaker and wait for one.
2. Status words from the server, such as `done` and `completed`, are shown as the server writes them.
3. The app always acts as the demo student, `student_001`. There is no sign in, as `docs/api.md` says.
4. Standing payments, reminders, the monthly note, trace and precheck have endpoints but no screens yet.
