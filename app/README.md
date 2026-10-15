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
3. A confirmation card built from the reply's `confirmation` field: the warning, the action, every route with the selected one marked, and the council's advice when present. The council's runner up is shown only when its disagreement score is above 0.4, the backend's `RUNNER_UP_DISAGREEMENT`, as the reply text does, and the reasons it was asked are shown as short labels in the chosen language; an id the app does not know is left off. A route is marked Blocked only when it has a blocked reason, its limit is not ok, or its status is down; a degraded route is still offered by the loop, so it is not marked. A route's blocked reason and the knowledge entry it cites, its `rule_id`, are shown as the server sends them; the app keeps no copy of the knowledge base. The token is kept only in memory, inside the card, and is sent back to `/confirm` exactly as it came, once. A token the server does not accept, because it expired, was used or was never issued, comes back as a normal reply that says nothing was sent, and the app shows it as one.
4. The two sentences code writes in every reply, shown on their own lines: each blocked request sentence at the top, and the sentence that begins `This turn:`, `Neste turno:` or `本轮：` at the bottom. The app reads them from the reply's `blocked` and `turn_summary` fields. Only when a field is absent, as from a server older than those fields, does it find that sentence by its wording.
5. The lost card rescue, driven only by `rescue.do_now`, for all seven values. Its fields take typed words only: pasting and dropping are refused. An empty identity answer is never sent, because the server would count it as a wrong one, and the answer is cleared as soon as it is sent.
6. The ledger, under Advanced on the Activity tab: every entry, newest first, with the result of verify above it: whether the chain is intact and the first broken entry, the anchor status, the integrity hold, and whether demo keys are signing.
7. A welcome screen, shown on opening before the tabs: the logo, one sentence on what Lifeline is for, three short cards to swipe or tap through, on what Lifeline does, what it never does and how it works, and one button, Continue as the demo student, with a line saying the demo runs as one demo student with demo limits, no real money moves and sign in is not built. It has no password field and no account. Continue opens the onboarding, and the Welcome button in the top bar brings it back. Nothing remembers a visit, so it shows on every opening. `?welcome=off` in the address skips it; the browser tests use that.
8. The Guide tab, after Activity: six sections for the moments a student meets, paying rent abroad, a message about money, a lost card, money from or to China, money from India or to Brazil, and reading the ledger, then How Lifeline protects you in six sections. Example sentences can be tapped to put their words in the message box, never in the paste box. When the tab is shown it reads `GET /ledger/{user_id}/verify` once and shows the result, with a line when development keys are signing. Its sentences are in `src/guide-content.js` and `src/i18n.js`.
9. The logo, an original mark drawn in `src/logo.js`: one continuous line with a single heartbeat pulse, in the accent colour, beside the wordmark Lifeline. It is in the top bar, on the welcome screen, and in `index.html` as the favicon, drawn from the same path.
10. The onboarding, after the welcome. First three questions about the trip: home, where the student will study, and the purpose. The two country lists hold every country with its flag and its name in the chosen language, from the browser's own `Intl.DisplayNames`. Brazil, China, India and Singapore come first, in bold, because `rails/knowledge` has entries for them; any other country can be chosen and the app says Lifeline has no sourced rules for it yet. The trip stays in page memory only: nothing is sent and nothing is written to browser storage. Skip keeps the plan as it is on file.
11. Then the safety net, which collects nothing it cannot keep. Four steps are the four fields `update_plan` changes at tier 1, `PLAN_UPDATE_FIELDS` in `contracts/schemas.py`: the backup card, which can only be another of the plan's own cards and never the main card; the backup route, Wise or Bank transfer; whether a phone wallet holds the card; and the cash plan, the cash pickup entry `sg_cash_pickup_001` or none. Each shows what is on file. Three steps are read only: the trusted contact, the emergency money and the safety question say what is on file and that chat cannot change them, because the engine refuses them under rule R04, and that changing a limit is never done in chat, being tier 3 by design. They have no fields, so no phone, email or answer is ever asked for. The steps end in one message naming only what changed, with the ids the plan holds, such as "Please update my plan: my backup route is Bank transfer (bank_wire); no phone wallet holds my card; my cash plan is empty." The button puts it in the message box, where the student reads it and sends it through `/chat` as their own words; the engine checks it, and the ledger records a proposal, a decision at T1 and an execution whose `result.plan_updated` names the fields. The plan on file is the plan of `fixtures/demo_user.yaml` with every `plan_updated` that `GET /ledger` records, as the server itself rebuilds it.
12. The trip tailors the app: the greeting on Home and at the top of Chat names the place of study, the money from home card on Home names the home country, and an empty chat offers a starter about money from that country. China, India and Brazil have their own starter, because `rails/knowledge` has entries on money from them.
13. The Me page, from the Me button in the top bar: the trip and the plan on file, each with Change, marked Sample because it is the demo student's plan with the changes the ledger records; how Lifeline chooses a route, in one sentence, Lifeline picks the cheapest route not marked Simulated, and simulated routes follow a real rail's rules, for practice; the checks of `POST /precheck` that fit the trip, money from China, arriving in China or turning on Pix, each run only when tapped because each writes a ledger entry, with the documents, the review triggers and the entry ids the server returns; and sign in, marked Coming soon.
14. Home, the first tab after the onboarding: the greeting, a Reminders button that opens the reminders of `GET /reminders/{user_id}`, the due ones first with their count on the button, and four cards. Pay rent, Money from home and Spot a scam each show the words they send and send them to Chat at once, in `text`. Lost card opens the Lost card tab, because a rescue starts from the student's own account of what happened. There is no balance, because the API has no endpoint for one.
15. Chat polish. An empty chat offers starters that send at once: the agreed rent sentence, the money from home question when the trip names a home, and how to spot a scam. They go once a message is sent. Routes on the confirmation card have friendly names, Wise, Pix and Bank transfer, with the Simulated tag kept and the rail id kept on the page; any other rail shows its id. The chosen route has a tick, and the card says how the route was chosen: Lifeline picks the cheapest route not marked Simulated, and simulated routes follow a real rail's rules, for practice. A Copy button sits under a reply only when it holds the model's words, and it copies only those words, never the sentences code wrote.
16. The Lost card start has one tap answers: three for a lost card and two for a stolen one. A tap fills the box with those words, which the student can change; nothing is sent until Start, pasting stays refused, and each step still has one confirm.
17. The Activity tab: the ledger in plain words, grouped under Today, Yesterday or the date, newest first. A line is written only for a payment, a refusal, a freeze, a plan update, a rescue start, the replacement card steps, the family notice and a provider check, and says only what its entry says, with the entry's number. Every entry is under Advanced, with the chain check.
18. Book and pay safely, from a card on Home: four checks before booking or paying, a rent deposit checklist whose ticks live only in the page, and apps to start from, by name only, in alphabetical order within each group: Singapore Airlines, Skyscanner and Trip.com for flights, Trip.com and Trivago for places to stay, HeyMax and YouTrip for paying abroad. It has no links, logos, prices or ratings, and it says Lifeline isn't partnered with or paid by any of these apps. Check a message opens Chat with the question typed and the paste box open, so the message goes in `pasted_text`, and nothing is sent until the student taps Send.

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

`npm test` runs the unit tests. Two of them read the backend's own files, so they fail if lane A changes something the app copies: the wording of the two code written sentences in `core/agent.py`, which the app now uses only as a fallback, and the list of `do_now` values in `contracts/schemas.py`. Three more do the same for the onboarding: the countries listed first must be the countries of `rails/knowledge`, the sample plan on Me must be the plan of `fixtures/demo_user.yaml`, and every check on Me must be a kind `rails/fake_router.py` answers.

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
| `welcome_how_3` | Every step is recorded where you can see it, on the Activity tab. | Cada passo fica registrado onde você pode ver, na aba Atividade. | 每一步都记录在您能看到的地方，就在「动态」标签页。 |
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
| `guide_ledger_1` | Under Advanced, the Activity tab lists every step Lifeline took, newest first. Each entry carries a hash, a fingerprint of its contents and of the entry before it. | Em Avançado, a aba Atividade lista cada passo do Lifeline, do mais novo ao mais antigo. Cada entrada leva um hash, uma impressão digital do seu conteúdo e da entrada anterior. | 「动态」标签页的「高级」中按从新到旧列出 Lifeline 的每一步。每条记录都带有一个哈希，即它的内容和上一条记录的指纹。 |
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
| `protect_recorded_3` | You can open every entry under Advanced on the Activity tab. | Você pode abrir cada entrada em Avançado, na aba Atividade. | 您可以在「动态」标签页的「高级」中打开每一条记录。 |
| `protect_not_title` | What Lifeline does not do | O que o Lifeline não faz | Lifeline 不做什么 |
| `protect_not_1` | It holds no money and is not a licensed payment institution. It gives no investment advice. It never changes your limits in chat. It never asks for your identity documents. | Não guarda dinheiro e não é uma instituição de pagamento licenciada. Não dá conselhos de investimento. Nunca muda os seus limites pelo chat. Nunca pede os seus documentos de identidade. | 它不保管资金，也不是持牌支付机构。它不提供投资建议。它从不在对话中更改您的限额。它从不索要您的身份证件。 |
| `protect_demo_title` | What this demo is | O que é esta demonstração | 这个演示是什么 |
| `protect_demo_1` | Every rail here is a fixture or a simulation and no real money moves. The API runs on this machine only, with no sign in, for one demo student. | Cada trilho aqui é uma fixture ou uma simulação e nenhum dinheiro real se move. A API roda só nesta máquina, sem login, para um único estudante de demonstração. | 这里的每个通道都是固定样例或模拟，不会转移真实资金。API 只在本机运行，没有登录，只服务一名演示学生。 |
| `protect_demo_2` | The full security self assessment and the known limitations are in docs/self_assessment.md in the repository. | A autoavaliação de segurança completa e as limitações conhecidas estão em docs/self_assessment.md no repositório. | 完整的安全自评报告和已知局限，见代码仓库中的 docs/self_assessment.md。 |

### Onboarding, tailoring and Me

The labels of the onboarding, the tailoring and the Me page, as `src/i18n-onboarding.js` holds them, wait for a native speaker too. `tests/unit/onboarding-words.test.js` fails when this table no longer holds the words the app shows.

| Key | English | Portuguese | Chinese |
| --- | --- | --- | --- |
| `open_me` | Me | Eu | 我的 |
| `onb_trip_title` | Your trip | A sua viagem | 您的行程 |
| `onb_trip_intro` | Three questions so Lifeline can speak to your trip. Nothing you choose here is sent to the server. | Três perguntas para o Lifeline falar da sua viagem. Nada do que você escolher aqui é enviado ao servidor. | 回答三个问题，Lifeline 就能针对您的行程说话。您在这里的选择不会发送到服务器。 |
| `onb_home` | Where is home? | Qual é o seu país de origem? | 您来自哪里？ |
| `onb_study` | Where will you study? | Onde você vai estudar? | 您将在哪里学习？ |
| `onb_choose_country` | Choose a country | Escolha um país | 选择国家或地区 |
| `onb_group_on_file` | Rules on file | Regras registradas | 已收录规则 |
| `onb_group_others` | Every other country | Todos os outros países | 其他所有国家或地区 |
| `onb_no_rules` | Lifeline has no sourced rules for {place} yet, so it cannot check that country's rules for you. | O Lifeline ainda não tem regras com fonte para este país ({place}), então não pode conferir as regras dele para você. | Lifeline 尚未收录{place}有来源的规则，因此无法为您核对当地规则。 |
| `onb_purpose` | What is the trip for? | Qual é o motivo da viagem? | 这次出行的目的是什么？ |
| `purpose_exchange` | Exchange | Intercâmbio | 交换 |
| `purpose_degree` | Full degree | Graduação completa | 攻读完整学位 |
| `purpose_internship` | Internship | Estágio | 实习 |
| `purpose_leisure` | Leisure and travel | Lazer e viagem | 休闲旅行 |
| `purpose_family` | Visiting friends and family | Visitar amigos e família | 探亲访友 |
| `purpose_work` | Work or a conference | Trabalho ou conferência | 工作或参加会议 |
| `onb_continue` | Continue | Continuar | 继续 |
| `onb_skip` | Skip | Pular | 跳过 |
| `onb_skip_note` | Skip keeps the demo student's sample plan. | Pular mantém o plano de exemplo do estudante de demonstração. | 跳过将保留演示学生的示例计划。 |
| `onb_back` | Back | Voltar | 返回 |
| `onb_next` | Next | Próximo | 下一步 |
| `onb_step_n` | Step {n} of {total} | Etapa {n} de {total} | 第 {n} 步，共 {total} 步 |
| `onb_plan_title` | Your safety net | A sua rede de segurança | 您的安全网 |
| `onb_plan_intro` | Four parts of your plan can change in chat: the backup card, the backup route, the phone wallet and the cash plan. Each step shows what is on file. At the end Lifeline writes one message for you to send, and the engine checks it like any request of yours. | Quatro partes do seu plano podem mudar pelo chat: o cartão reserva, a rota reserva, a carteira do celular e o plano de dinheiro em espécie. Cada etapa mostra o que está registrado. No fim, o Lifeline escreve uma mensagem para você enviar, e o motor a confere como qualquer pedido seu. | 您计划中有四项可以在对话中更改：备用卡、备用路线、手机钱包和现金方案。每一步都会显示当前记录。最后，Lifeline 会为您写好一条消息由您发送，规则引擎会像核查您的任何请求一样核查它。 |
| `onb_on_file` | On file: {value} | Registrado: {value} | 当前记录：{value} |
| `onb_backup_card_q` | Which card is your backup? | Qual é o seu cartão reserva? | 哪张卡是您的备用卡？ |
| `onb_backup_card_hint` | A backup must be one of your plan's own cards and never the main card, {main}. | O reserva precisa ser um dos cartões do seu próprio plano e nunca o cartão principal, {main}. | 备用卡必须是您计划中自己的卡，且不能是主卡（{main}）。 |
| `onb_backup_route_q` | Which route should payments use if your card is lost? | Que rota os pagamentos devem usar se você perder o cartão? | 丢卡时付款应使用哪条路线？ |
| `onb_backup_route_hint` | Only routes not marked Simulated are offered. | Só aparecem rotas que não estão marcadas como Simuladas. | 这里只提供未标为模拟的路线。 |
| `onb_wallet_q` | Does a phone wallet hold your card? | Alguma carteira do celular guarda o seu cartão? | 您的卡是否已绑定手机钱包？ |
| `onb_wallet_yes` | Yes, a phone wallet holds my card | Sim, uma carteira do celular guarda o meu cartão | 是，我的卡已绑定手机钱包 |
| `onb_wallet_no` | No phone wallet holds my card | Nenhuma carteira do celular guarda o meu cartão | 否，我的卡没有绑定手机钱包 |
| `onb_cash_q` | What is your cash plan if you cannot pay by card? | Qual é o seu plano de dinheiro em espécie se não puder pagar com cartão? | 无法刷卡时，您的现金方案是什么？ |
| `onb_cash_pickup` | A cash pickup in Singapore, knowledge entry sg_cash_pickup_001 | Uma retirada de dinheiro em Singapura, entrada sg_cash_pickup_001 | 在新加坡取现，知识条目 sg_cash_pickup_001 |
| `onb_cash_none` | No cash plan | Nenhum plano de dinheiro em espécie | 没有现金方案 |
| `onb_contact_title` | Trusted contact | Contato de confiança | 信任联系人 |
| `onb_contact_ro` | On file: {name}, by {channel}. Lifeline holds only a name and a channel, never a phone number or an email. | Registrado: {name}, por {channel}. O Lifeline guarda só um nome e um canal, nunca um telefone ou um email. | 当前记录：{name}，通过{channel}。Lifeline 只保存姓名和联系方式类型，从不保存电话号码或邮箱。 |
| `onb_contact_why` | Chat cannot change the trusted contact: the engine refuses it under rule R04. | O chat não pode mudar o contato de confiança: o motor recusa isso pela regra R04. | 对话无法更改信任联系人：规则引擎会依据规则 R04 拒绝。 |
| `onb_money_title` | Emergency money | Dinheiro de emergência | 应急资金 |
| `onb_money_ro` | On file: {amount} {currency}. In a rescue it is only proposed, to your own account, and nothing moves until you confirm it. | Registrado: {amount} {currency}. Num resgate ele só é proposto, para a sua própria conta, e nada se move até você confirmar. | 当前记录：{amount} {currency}。救援时只会提议转到您自己的账户，您确认之前不会转出任何资金。 |
| `onb_money_why` | Chat cannot change this amount: the engine refuses it under rule R04. Changing a limit is never done in chat: it is tier 3 by design. | O chat não pode mudar este valor: o motor recusa isso pela regra R04. Mudar um limite nunca é feito pelo chat: é nível 3 por definição. | 对话无法更改这个金额：规则引擎会依据规则 R04 拒绝。更改限额从不在对话中进行：按设计这属于第 3 级。 |
| `onb_question_title` | Safety question | Pergunta de segurança | 安全问题 |
| `onb_question_ro` | On file: {question} The answer is never shown or asked for here. | Registrada: {question} A resposta nunca é mostrada nem pedida aqui. | 当前记录：{question} 这里从不显示也从不询问答案。 |
| `onb_question_why` | Chat cannot change the safety question or its answer: the engine refuses it under rule R04. | O chat não pode mudar a pergunta de segurança nem a resposta: o motor recusa isso pela regra R04. | 对话无法更改安全问题或答案：规则引擎会依据规则 R04 拒绝。 |
| `onb_rescue_note` | In this demo the live rescue asks the sample plan's question: What are the last four characters of your student pass number? | Nesta demonstração, o resgate ao vivo faz a pergunta do plano de exemplo: quais são os quatro últimos caracteres do número do seu cartão de estudante? | 在本演示中，实时救援使用示例计划的问题：您学生证号码的最后四位是什么？ |
| `onb_message_title` | Your message | A sua mensagem | 您的消息 |
| `onb_message_intro` | Lifeline wrote this from your choices. Put it in the message box, read it, and send it yourself. The engine checks it at tier 1, and the ledger records the change. | O Lifeline escreveu isto a partir das suas escolhas. Coloque na caixa de mensagem, leia e envie você mesmo. O motor confere no nível 1, e o registro guarda a mudança. | Lifeline 根据您的选择写好了这条消息。请把它放进消息框，读一遍，然后由您自己发送。规则引擎按第 1 级核查，账本会记录这次更改。 |
| `onb_message_none` | Everything is as it is on file, so there is nothing to send. | Tudo está como está registrado, então não há nada para enviar. | 一切都与当前记录相同，所以无需发送。 |
| `onb_put_in_chat` | Put it in the message box | Colocar na caixa de mensagem | 放进消息框 |
| `onb_done` | Done | Concluir | 完成 |
| `msg_plan_update` | Please update my plan: {parts}. | Por favor, atualize o meu plano: {parts}. | 请更新我的计划：{parts}。 |
| `msg_join` | ;  | ;  | ； |
| `msg_backup_card` | my backup card is my {name} ({id}) | o meu cartão reserva é o meu {name} ({id}) | 我的备用卡是我的 {name}（{id}） |
| `msg_backup_route` | my backup route is {name} ({rail}) | a minha rota reserva é {name} ({rail}) | 我的备用路线是{name}（{rail}） |
| `msg_wallet_yes` | a phone wallet holds my card | uma carteira do celular guarda o meu cartão | 我的卡已绑定手机钱包 |
| `msg_wallet_no` | no phone wallet holds my card | nenhuma carteira do celular guarda o meu cartão | 我的卡没有绑定手机钱包 |
| `msg_cash_pickup` | my cash plan is the cash pickup in Singapore (sg_cash_pickup_001) | o meu plano de dinheiro em espécie é a retirada em Singapura (sg_cash_pickup_001) | 我的现金方案是在新加坡取现（sg_cash_pickup_001） |
| `msg_cash_none` | my cash plan is empty | o meu plano de dinheiro em espécie fica vazio | 我的现金方案为空 |
| `rail_wise` | Wise | Wise | Wise |
| `rail_bank_wire` | Bank transfer | Transferência bancária | 银行转账 |
| `rail_sim_pix` | Pix | Pix | Pix |
| `channel_whatsapp` | WhatsApp | WhatsApp | WhatsApp |
| `channel_wechat` | WeChat | WeChat | 微信 |
| `channel_telegram` | Telegram | Telegram | Telegram |
| `channel_sms` | Text message | Mensagem de texto | 短信 |
| `channel_phone_call` | Phone call | Ligação | 电话 |
| `channel_email` | Email | Email | 邮件 |
| `hello_study` | Hello. Lifeline is ready for your time in {place}. | Olá. O Lifeline está pronto para o seu período de estudos. Destino: {place}. | 您好。Lifeline 已准备好陪您在{place}学习。 |
| `hello_plain` | Hello. Lifeline is ready to help. | Olá. O Lifeline está pronto para ajudar. | 您好。Lifeline 随时为您提供帮助。 |
| `from_home` | Money from {place} | Dinheiro do seu país: {place} | 来自{place}的钱 |
| `from_home_plain` | Money from home | Dinheiro do seu país | 来自家里的钱 |
| `starter_home_cn` | My family wants to send money from China. What will the bank ask for? | Minha família quer enviar dinheiro da China. O que o banco vai pedir? | 我的家人想从中国给我汇钱。银行会要求什么材料？ |
| `starter_home_in` | My parents want to send money from India. How does that work? | Meus pais querem enviar dinheiro da Índia. Como funciona? | 我的父母想从印度给我汇钱。流程是怎样的？ |
| `starter_home_br` | How can my family send me money from Brazil? | Como minha família pode me enviar dinheiro do Brasil? | 我的家人怎样从巴西给我汇钱？ |
| `starter_home_other` | How can my family send me money from {place}? | Como minha família pode me enviar dinheiro? País de origem: {place}. | 我的家人怎样从{place}给我汇钱？ |
| `me_title` | Me | Eu | 我的 |
| `me_trip` | Your trip | A sua viagem | 您的行程 |
| `me_no_trip` | No trip set, so Lifeline speaks in general terms. | Nenhuma viagem definida, então o Lifeline fala de forma geral. | 尚未设置行程，因此 Lifeline 只做一般性说明。 |
| `me_trip_line` | {purpose}, from {home} to {study} | {purpose}. Origem: {home}. Destino: {study}. | {purpose}，从{home}到{study} |
| `me_change` | Change | Mudar | 更改 |
| `me_net` | Your safety net | A sua rede de segurança | 您的安全网 |
| `me_sample` | Sample | Exemplo | 示例 |
| `me_sample_note` | This is the demo student's sample plan, with every change your ledger records. The live rescue reads it. | Este é o plano de exemplo do estudante de demonstração, com cada mudança que o seu registro guarda. O resgate ao vivo lê este plano. | 这是演示学生的示例计划，并包含您账本记录的每一次更改。实时救援读取的就是它。 |
| `me_card` | Main card | Cartão principal | 主卡 |
| `me_backup_card` | Backup card | Cartão reserva | 备用卡 |
| `me_backup_route` | Backup route | Rota reserva | 备用路线 |
| `me_wallet` | Phone wallet | Carteira do celular | 手机钱包 |
| `me_cash` | Cash plan | Dinheiro em espécie | 现金方案 |
| `me_yes` | Yes | Sim | 是 |
| `me_no` | No | Não | 否 |
| `me_none` | None | Nenhum | 无 |
| `sample_question` | What are the last four characters of your student pass number? | Quais são os quatro últimos caracteres do número do seu cartão de estudante? | 您学生证号码的最后四位是什么？ |
| `me_question` | Safety question | Pergunta de segurança | 安全问题 |
| `me_contact` | Trusted contact | Contato de confiança | 信任联系人 |
| `me_contact_line` | {name}, by {channel} | {name}, por {channel} | {name}，通过{channel} |
| `me_money` | Emergency money | Dinheiro de emergência | 应急资金 |
| `me_routes` | How routes are chosen | Como as rotas são escolhidas | 如何选择路线 |
| `me_route_rule` | Lifeline picks the cheapest route not marked Simulated. Simulated routes follow a real rail's rules, for practice. | O Lifeline escolhe a rota mais barata que não está marcada como Simulada. As rotas simuladas seguem as regras de um trilho real, para praticar. | Lifeline 选择未标为模拟的最便宜路线。模拟路线遵循真实通道的规则，用于练习。 |
| `me_checks` | What a provider may ask | O que um provedor pode pedir | 服务商可能会要求什么 |
| `me_check_intro` | Each check asks the server and writes one entry to your ledger, so it runs only when you tap it. | Cada verificação consulta o servidor e grava uma entrada no seu registro, por isso só roda quando você toca nela. | 每次核查都会询问服务器，并在您的账本中写入一条记录，所以只在您点按时运行。 |
| `me_check_button` | Check: {what} | Verificar: {what} | 核查：{what} |
| `check_remit_from_china` | money from China | dinheiro da China | 从中国汇款 |
| `check_arrive_in_china` | arriving in China | chegada à China | 抵达中国 |
| `check_enable_pix` | turning on Pix | ativar o Pix | 开通 Pix |
| `me_check_none` | Lifeline has no check on file for this trip yet. | O Lifeline ainda não tem verificação registrada para esta viagem. | Lifeline 尚未收录适用于此行程的核查。 |
| `me_check_documents` | Documents likely asked for | Documentos que provavelmente serão pedidos | 可能需要的材料 |
| `me_check_triggers` | What may lead to a review | O que pode levar a uma análise | 可能引发审核的情况 |
| `me_check_sources` | Sources: {ids} | Fontes: {ids} | 来源：{ids} |
| `me_check_not_ready` | The server says this is not ready yet. | O servidor diz que isto ainda não está pronto. | 服务器表示目前尚未就绪。 |
| `me_signin` | Sign in is coming soon. This demo runs as one demo student. | O login chega em breve. Esta demonstração funciona como um único estudante de demonstração. | 登录功能即将推出。本演示以一名演示学生运行。 |
| `me_coming_soon` | Coming soon | Em breve | 即将推出 |
| `me_close` | Close | Fechar | 关闭 |
| `route_source` | Source: {id} | Fonte: {id} | 来源：{id} |

### Home, Activity, chat polish and Lost card

The labels of Home, Activity, the chat polish and the Lost card one tap answers, as `src/i18n-home.js` holds them, wait for a native speaker too. `tests/unit/home-words.test.js` fails when this table no longer holds the words the app shows.

| Key | English | Portuguese | Chinese |
| --- | --- | --- | --- |
| `tab_home` | Home | Início | 首页 |
| `tab_activity` | Activity | Atividade | 动态 |
| `home_bell` | Reminders | Lembretes | 提醒 |
| `home_bell_due` | {count} due | {count} para agora | {count} 项到期 |
| `home_reminders_title` | Coming up | Próximos | 即将到来 |
| `home_reminders_none` | Nothing coming up. | Nada por vir. | 暂无提醒。 |
| `home_due` | Due | Para agora | 已到期 |
| `home_no_date` | No date | Sem data | 无日期 |
| `home_cards_title` | What do you need? | Do que você precisa? | 您需要什么帮助？ |
| `home_card_rent` | Pay rent | Pagar o aluguel | 交房租 |
| `home_card_scam` | Spot a scam | Identificar um golpe | 识别诈骗 |
| `home_card_lost` | Lost card | Cartão perdido | 丢卡 |
| `home_card_lost_sub` | Opens the lost card steps. | Abre as etapas de cartão perdido. | 打开丢卡处理步骤。 |
| `home_sends` | Sends: {words} | Envia: {words} | 发送：{words} |
| `starter_scam` | How do I spot a scam message? | Como identifico uma mensagem de golpe? | 我怎样识别诈骗消息？ |
| `starter_home_plain` | How can my family send me money from home? | Como minha família pode me enviar dinheiro do meu país? | 我的家人怎样从国内给我汇钱？ |
| `chat_starters_title` | Try asking | Experimente perguntar | 试着问问 |
| `copy` | Copy | Copiar | 复制 |
| `copied` | Copied | Copiado | 已复制 |
| `copy_failed` | Could not copy. Select the text instead. | Não foi possível copiar. Selecione o texto. | 无法复制，请手动选择文字。 |
| `rescue_quick_label` | Tap one to fill in the box, or type your own words. | Toque em uma opção para preencher a caixa, ou digite com as suas palavras. | 点按一项填入输入框，或用您自己的话输入。 |
| `quick_lost_transport` | I lost it on transport | Perdi no transporte | 在交通工具上丢了 |
| `quick_lost_somewhere` | I left it somewhere | Esqueci em algum lugar | 落在某个地方了 |
| `quick_lost_cant_find` | I can't find it | Não encontro | 找不到了 |
| `quick_stolen_bag` | It was taken from my bag | Tiraram da minha bolsa | 从我包里被拿走了 |
| `quick_stolen_phone` | My phone and card were taken | Levaram meu celular e o cartão | 手机和卡都被拿走了 |
| `activity_intro` | What happened, in plain words. Every entry is under Advanced. | O que aconteceu, em palavras simples. Cada entrada está em Avançado. | 用简单的话说明发生了什么。每一条记录都在「高级」中。 |
| `activity_empty` | Nothing here yet. | Nada aqui ainda. | 暂无内容。 |
| `activity_today` | Today | Hoje | 今天 |
| `activity_yesterday` | Yesterday | Ontem | 昨天 |
| `activity_advanced` | Advanced: every ledger entry | Avançado: cada entrada do registro | 高级：账本中的每一条记录 |
| `activity_seq` | Ledger entry #{seq} | Entrada #{seq} do registro | 账本记录 #{seq} |
| `act_sent` | Sent {amount} {currency} to {payee} | {amount} {currency} enviados para {payee} | 已向{payee}发送 {amount} {currency} |
| `act_sent_status` | {amount} {currency} to {payee}: {status} | {amount} {currency} para {payee}: {status} | 向{payee}发送 {amount} {currency}：{status} |
| `act_refused_paste` | Lifeline refused a request that did not come from your own words | O Lifeline recusou um pedido que não veio das suas próprias palavras | Lifeline 拒绝了一个并非出自您本人话语的请求 |
| `act_refused` | Lifeline refused a request: {type} | O Lifeline recusou um pedido: {type} | Lifeline 拒绝了一个请求：{type} |
| `act_frozen` | Card frozen | Cartão bloqueado | 卡已冻结 |
| `act_freeze_status` | Card freeze: {status} | Bloqueio do cartão: {status} | 冻结卡：{status} |
| `act_rescue_started` | Lost card rescue started | Resgate de cartão perdido iniciado | 丢卡救援已启动 |
| `act_replacement` | Replacement card steps given | Etapas para um cartão novo informadas | 已提供补办新卡的步骤 |
| `act_family_told` | {name} was told by {channel} | Aviso enviado para {name} por {channel} | 已通过{channel}通知{name} |
| `act_plan_updated` | Your plan changed: {fields} | O seu plano mudou: {fields} | 您的计划已更改：{fields} |
| `act_precheck` | Lifeline checked what a provider may ask | O Lifeline verificou o que um provedor pode pedir | Lifeline 已核查服务商可能要求的内容 |
| `payee_landlord_sp` | your landlord | o seu locador | 您的房东 |
| `payee_self_sg` | your own Singapore account | a sua própria conta em Singapura | 您自己的新加坡账户 |
| `payee_student_001` | the student | o estudante | 学生 |
| `payee_unknown` | a payee | um destinatário | 收款人 |

### Book and pay safely

The labels of Book and pay safely, as `src/i18n-book.js` holds them, wait for a native speaker too. `tests/unit/book.test.js` fails when this table no longer holds the words the app shows. The app names are not translated.

| Key | English | Portuguese | Chinese |
| --- | --- | --- | --- |
| `home_book` | Booking flights or a place to stay? | Vai reservar voo ou hospedagem? | 要订机票或住处吗？ |
| `home_book_open` | Book and pay safely | Reserve e pague com segurança | 安全预订与付款 |
| `book_title` | Book and pay safely | Reserve e pague com segurança | 安全预订与付款 |
| `book_intro` | Flights, places to stay and rent abroad: where to start, and what to check before you pay. | Voos, hospedagem e aluguel no exterior: por onde começar e o que conferir antes de pagar. | 海外机票、住宿和租房：从哪里开始，以及付款前要核对什么。 |
| `book_checks_title` | Before you book or pay | Antes de reservar ou pagar | 预订或付款之前 |
| `book_check_1` | Open the booking app or website yourself. Do not book from a link someone sent you. | Abra você mesmo o app ou o site de reservas. Não reserve por um link que alguém mandou. | 请自己打开预订应用或网站，不要通过别人发来的链接预订。 |
| `book_check_2` | If a host or landlord asks you to pay outside the booking app, by bank transfer or in a chat, stop and check first. | Se um anfitrião ou locador pedir pagamento fora do app de reservas, por transferência ou no chat, pare e confira antes. | 如果房东或民宿主人要求您在预订应用之外付款，比如银行转账或在聊天中付款，请先停下来核实。 |
| `book_check_3` | Pay by card or by a transfer you can trace. Do not pay by gift card or crypto. | Pague com cartão ou com uma transferência rastreável. Não pague com vale presente nem com cripto. | 请用银行卡或可追踪的转账付款，不要用礼品卡或加密货币付款。 |
| `book_check_4` | Not sure about a message? Paste it into Chat and ask Lifeline before you pay. | Na dúvida sobre uma mensagem? Cole no Chat e pergunte ao Lifeline antes de pagar. | 不确定某条消息？付款前请把它粘贴到对话中，问问 Lifeline。 |
| `book_check_button` | Check a message in Chat | Conferir uma mensagem no Chat | 在对话中核查一条消息 |
| `book_check_words` | Is this booking message a scam? | Esta mensagem de reserva é golpe? | 这条预订消息是诈骗吗？ |
| `book_deposit_title` | Before you pay a rent deposit | Antes de pagar o depósito do aluguel | 支付租房押金之前 |
| `book_deposit_intro` | Tick each one as you go. This page keeps nothing, so the ticks are gone when you close it. | Marque cada item conforme avança. Esta página não guarda nada, então as marcas somem quando você a fecha. | 逐项勾选。本页不保存任何内容，关闭页面后勾选就会消失。 |
| `book_deposit_1` | You have seen the place, in person or on a live video call. | Você viu o lugar, pessoalmente ou numa chamada de vídeo ao vivo. | 您已经亲自或通过实时视频看过房子。 |
| `book_deposit_2` | The landlord's name matches the agreement. | O nome do locador é o mesmo do contrato. | 房东姓名与合同一致。 |
| `book_deposit_3` | You have a written agreement with the rent, the deposit and the dates. | Você tem um contrato escrito com o aluguel, o depósito e as datas. | 您有书面合同，写明租金、押金和日期。 |
| `book_deposit_4` | You are paying an account you can trace, and you will get a receipt. | Você paga para uma conta rastreável e vai receber um recibo. | 您付款到可追踪的账户，并会收到收据。 |
| `book_apps_title` | Apps to start from | Apps para começar | 可以从这些应用开始 |
| `book_apps_order` | Names only, in alphabetical order within each group. No links, prices or ratings. | Só os nomes, em ordem alfabética dentro de cada grupo. Sem links, preços ou avaliações. | 只列名称，每组按字母顺序排列。没有链接、价格或评分。 |
| `book_apps_note` | Lifeline isn't partnered with or paid by any of these apps. | O Lifeline não tem parceria com nenhum desses apps e não recebe nada deles. | Lifeline 与这些应用均无合作，也不从中获得任何报酬。 |
| `book_group_flights` | Flights | Voos | 机票 |
| `book_group_stays` | Places to stay | Hospedagem | 住宿 |
| `book_group_paying` | Paying abroad | Pagar no exterior | 海外付款 |
| `book_flights_hint` | Or any airline's own app, to book direct. | Ou o app da própria companhia aérea, para reservar direto. | 也可以用任何航空公司自己的应用直接预订。 |
| `book_close` | Back to Home | Voltar ao Início | 返回首页 |

## Known gaps

1. The Portuguese and Chinese labels were written without a native speaker and wait for one.
2. Status words from the server, such as `done` and `completed`, are shown as the server writes them.
3. The app always acts as the demo student, `student_001`. There is no sign in, as `docs/api.md` says.
4. Standing payments, the monthly note and trace have endpoints but no screens yet. Precheck has one, on Me, for three kinds, and reminders are read on Home.
5. The trusted contact, the emergency money and the safety question cannot change from the app, because chat cannot change them and the API has no other way to. The live rescue asks the sample plan's question.
