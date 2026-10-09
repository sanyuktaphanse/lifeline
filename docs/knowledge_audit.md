# Knowledge base audit

This is Stage 12 of the build program. It audits every entry in `rails/knowledge/` against the page its `source_url` names, as those pages stood on 9 October 2026. It changes no code and no entry. The fixes belong to lane B in their own pull request, and the last section of this file lists them.

## How the audit was done

Each entry was given to two checkers, A and B, who worked independently and did not see each other's findings or the entry's `note`, `checked_by` or `second_check_by`. Each checker opened the source page itself, with curl and a text extraction in memory, or with a direct fetch of the URL when curl could not read the page, and never used a search summary. The two Pix entries cite a PDF, which both checkers read by decompressing its text streams in memory. Each checker reported four points for every entry: whether the statement says what the page says, whether every number in the statement and in `values` appears on the page with the same unit and meaning, whether the page's own date agrees with `date_checked` or comes later, and whether the page covers the country, rail, audience and situation the entry claims. Quotations are copied from the page, so any hyphen or dash inside a quotation belongs to the source.

The age rule is the one in `tests/test_knowledge.py`: an entry fails when today minus `date_checked` is more than 30 days. An entry checked on 15 September 2026 therefore fails from 16 October 2026, and an entry checked on 8 October 2026 fails from 8 November 2026. An entry is marked aged when it fails today or will fail by 16 October 2026, seven days from the audit.

Five verdicts are used. Agreement means both checkers confirmed all four points. Disagreement means the page says something different from the entry. Unreachable means neither checker could open the page. Partly supported means the page confirms some points and is silent on others. Aged sits beside another verdict when the entry fails the age rule within seven days.

A page whose own date is earlier than `date_checked` passes the date point, because the entry was checked against that version. Where a page is years old, the audit says so, because an old page cannot show that a rule is still in force.

## 1. br_pix_instant_001

Source: https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Pix_Regulation/Resolution_BCB_1.pdf

`checked_by` is "SP" and `second_check_by` is empty. `date_checked` is 8 October 2026, 1 day before the audit. The age rule fails it from 8 November 2026.

Checker A opened the PDF with curl, which returned HTTP 200 and 537,607 bytes, after a direct fetch could not parse the binary. Every quotation below sits inside the PDF.

1. Statement: partly contradicted. The first sentence is confirmed: "Pix: payment scheme implemented by the Banco Central do Brasil that regulates the provision of payment services related to instant payment transactions" and "instant payment: electronic transfer of funds, in which the transfer of the payment order and the availability of funds to the payee user is in real time and for which service is available 24 (twenty-four) hours a day and every day of the year". The second sentence is broader than the page allows. The page defines a participant as "financial institution, payment institution or government entity that adheres to the Pix Regulation and meets the other requirements for joining the scheme", makes membership optional for "the National Treasury Secretariat, as a governing entity", and admits payment institutions that "do not meet the criteria provided for in the regulations in force to be authorized to operate by the Banco Central do Brasil".
2. Numbers: 24 hours is confirmed. `typical_duration_hours: 0` does not appear; the page says only "in real time".
3. Date: the heading reads "RESOLUTION BCB 1, OF AUGUST 12, 2020". The PDF's modification date and the HTTP Last-Modified header are 9 January 2024. The text cites later amendments, such as "BCB Resolution 80, of March 25, 2021". The page is earlier than `date_checked`, so the point passes, but the text is a January 2024 consolidation.
4. Scope: confirmed. The page covers Brazil and the Pix scheme as a whole.

Checker B opened the PDF the same way after a direct fetch failed with "the content provided is a PDF file in raw binary/encoded format that I cannot effectively parse".

1. Statement: the first sentence is confirmed by the same definitions of Pix and of instant payment. The second sentence is contradicted in part. B quotes the participant definition above, the rule that "Participation in Pix is mandatory for the financial institutions and payment institutions authorized to operate by the Banco Central do Brasil that have more than half a million active customer accounts", the optional membership of "the National Treasury Secretariat, as a governing entity", and the sentence that payment institutions which do not meet the criteria to be authorized "shall be considered members of the Brazilian Payments System (SPB) from the moment they submit a request to join Pix."
2. Numbers: 24 hours is confirmed; `typical_duration_hours: 0` is not stated as a number.
3. Date: the same marks as A, with the title dated 12 August 2020 and the file dated 9 January 2024. Earlier than `date_checked`.
4. Scope: confirmed for Brazil, the Pix rail and the scheme in general.

Verdict: disagreement. The entry says Pix participants are institutions authorized to operate by the Banco Central do Brasil, while the page also admits the National Treasury Secretariat and payment institutions that are not authorized; both checkers found it. Both also note that the value of zero hours is an inference from "real time", not a figure on the page.

## 2. br_pix_keys_002

Source: https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Pix_Regulation/Resolution_BCB_1.pdf

`checked_by` is "SP" and `second_check_by` is empty. `date_checked` is 8 October 2026, 1 day before the audit. The age rule fails it from 8 November 2026.

Checker A read the same PDF, with the quotations inside it.

1. Statement: confirmed. Article 45: "The following Pix keys may be used for linking with transactional accounts: I - cell phone number; II - e-mail address (e-mail); III - CPF registration number; IV - CNPJ registration number; and V - random key." A notes that Article 12 lists the key as one of several ways to start a payment, beside a dynamic QR code, a static QR code and a payment initiation service.
2. Numbers: there are none. All five key types match.
3. Date: 12 August 2020 in the heading and 9 January 2024 in the file. Earlier than `date_checked`.
4. Scope: confirmed for Brazil and Pix.

Checker B read the same PDF.

1. Statement: confirmed by the same Article 45 sentence, and by the definition "Pix key: information related to the holder of a transactional account that allows obtaining the information stored in the Transactional Accounts Identifier Directory (DICT) about the payee user and the corresponding transactional account". B notes that Article 5 also allows the payee's account details to be typed by hand, so a key is not the only way to reach a payee.
2. Numbers: all five key types appear verbatim.
3. Date: the same marks as A. Earlier than `date_checked`.
4. Scope: confirmed.

Verdict: agreement. Both checkers add that the statement is right as long as it is not read to mean a key is the only way to pay.

## 3. cn_fx_quota_001

Source: https://www.webull.com/news/13974173100655616

`checked_by` is "S" and `second_check_by` is empty. `date_checked` is 15 September 2026, 24 days before the audit. The age rule fails it from 16 October 2026.

Checker A opened the page with curl, HTTP 200. It is a Webull news page carrying an article credited to "Zhitongcaijing · 12/05/2025 12:01", a news aggregator.

1. Statement: partly confirmed. The quota is confirmed: "the annual facilitation quota policy of 50,000 US dollars for individuals remains unchanged." That view is credited to "A number of banking industry insiders". The page never mentions study, tuition or education, so the study abroad purpose is unsupported. The claim of January 2026 reporting is contradicted, because the article is dated 5 December 2025.
2. Numbers: 50,000 US dollars is confirmed: "Will an individual's annual foreign exchange purchase quota of 50,000 US dollars be affected?" January 2026 appears only as "from January 1, 2026", the start of a different rule.
3. Date: "Zhitongcaijing · 12/05/2025 12:01", 5 December 2025. Earlier than `date_checked`.
4. Scope: individuals in China in general. Silent on students and study abroad.

Checker B opened the page with curl, HTTP 200, and also found an aggregator.

1. Statement: the 50,000 dollar quota is confirmed with the same "remains unchanged" sentence. "Study", "tuition" and "abroad" do not appear anywhere in the raw page. The January 2026 claim is contradicted by the page date.
2. Numbers: 50,000 US dollars is confirmed with the same meaning.
3. Date: "Zhitongcaijing · 12/05/2025 12:01" and an embedded news time of 5 December 2025.
4. Scope: individuals in China in general; nothing on students or study abroad.

Verdict: disagreement, and aged. The entry says the quota was confirmed in January 2026 reporting, while the page is a report dated 5 December 2025; both checkers found it. The page is also silent on study abroad fees being a permitted purpose. The entry fails the age rule on 16 October 2026.

## 4. cn_edu_remit_002

Source: https://www.hsbc.com.cn/en-cn/international/products/education-payment/

`checked_by` is "S" and `second_check_by` is empty. `date_checked` is 15 September 2026, 24 days before the audit. The age rule fails it from 16 October 2026.

Checker A opened the page with curl, HTTP 200. It is HSBC Bank (China)'s own page.

1. Statement: partly confirmed. Remitting with documents outside the quota is confirmed in a section open by default: "Notes for overseas education remittances foreign exchange purchase not occupying SAFE annual facilitation quota: All submitted applications must include documents that meet regulatory and our bank's requirements." Tuition and living costs are confirmed: "such as tuition fees and living expenses for overseas schools". The page never frames this as remitting above the quota. The institution's account is confirmed only for the path inside the quota: "select your educational institute. The corresponding receiving account will match automatically with the institute's name." The two weeks advice is confirmed, but both sentences sit inside collapsed FAQ sections: "You are strongly recommended to allow more than 2 weeks for this process."
2. Numbers: the daily limit is confirmed in a notes section open by default: "Accumulative daily limits equivalent to USD50,000 shall apply to relevant transactions (including FX purchases from renminbi accounts and direct payments from foreign currency accounts)." It is a general note, not tied to the path outside the quota. "More than 2 weeks" is confirmed.
3. Date: the page carries no date. The only mark is "© Copyright. HSBC Bank (China) Company Limited 2026." The page warns "We may adjust the required document list and business rules from time to time."
4. Scope: narrower than the entry. "Applicable to all HSBC Premier, Premier Elite, Global Private Banking and Advance customers who hold a valid identity card in mainland China", and the service covers "more than 1,000 educational institutes in the US, UK, Canada, Australia and Hong Kong SAR". Singapore is not listed.

Checker B opened the page with curl, HTTP 200, the bank's own page.

1. Statement: the documents rule outside the quota is confirmed by the same section. The institution's account is partly confirmed, because the sentence sits under "To purchase foreign currency for payments within your personal FX quota". The two weeks advice is confirmed inside collapsed FAQ sections.
2. Numbers: USD50,000 daily is confirmed by the same note, which does not tie it to the path outside the quota. "More than 2 weeks" is confirmed.
3. Date: the page carries no date and no date metadata.
4. Scope: narrower than the entry, quoting the same customer tiers and the same five destinations; Singapore is not listed, and the rule is HSBC's own, not a rule for all of China.

Verdict: partly supported, and aged. The page is silent on two points: it does not say the payment goes to the institution's account on the path outside the quota, and it does not say the daily limit applies to that path. Its scope is narrower than the entry, since it covers only certain HSBC China customers paying institutions in the US, UK, Canada, Australia and Hong Kong. The page has no date, the two weeks advice sits in collapsed sections, and the entry fails the age rule on 16 October 2026.

## 5. cn_edu_docs_003

Source: https://www.hsbc.com.cn/en-cn/international/products/education-payment/

`checked_by` is "S" and `second_check_by` is empty. `date_checked` is 15 September 2026, 24 days before the audit. The age rule fails it from 16 October 2026.

Checker A opened the same HSBC page with curl, HTTP 200. The documents list sits in a notes section open by default.

1. Statement: mostly confirmed. "Valid documents for review include: payment proof ..., admission letter/student ID, student resident ID, passport, visa, and relationship certificates." "Relationship certificates: Birth certificate or household registration booklet." "Payment proof: Must include transaction amount, with details matching the institution, academy term, foreign exchange purchase and remittance amount with this transfer." The last sentence is contradicted in part. Documents are uploaded as images: "You must resubmit all valid documents via our mobile banking. We do not accept document supplements/replacements via email or other channels." and "Electronic image files shall be generated by photographing or scanning original documents or ID certificates. Electronic image files obtained by taking photos or scanning copies of the original documents are not acceptable."
2. Numbers: the statement has none. The page allows up to 5 images per upload section.
3. Date: no date on the page; only the 2026 copyright line.
4. Scope: HSBC China only.

Checker B opened the same page with curl, HTTP 200.

1. Statement: the document list, the relationship proof and the payment proof are confirmed with the same quotations. "Originals or scans of originals are accepted" is only partly supported, because the page accepts only uploaded photos or scans of originals: "Electronic image files shall be generated by photographing or scanning original documents or ID certificates. Electronic image files obtained by taking photos or scanning copies of the original documents are not acceptable." Nothing says physical originals are accepted.
2. Numbers: none in the statement. The page says "Each file upload section accepts up to 5 images."
3. Date: no date on the page.
4. Scope: narrower than the entry, the same HSBC customer and destination limits as entry 4.

Verdict: disagreement, and aged. The entry says originals or scans of originals are accepted, while the page accepts only photos or scans of originals uploaded through HSBC mobile banking; both checkers found it. The page covers HSBC China customers only, carries no date, and the entry fails the age rule on 16 October 2026.

## 6. cn_cdd_004

Source: https://www.webull.com/news/13974173100655616

`checked_by` is "S" and `second_check_by` is empty. `date_checked` is 15 September 2026, 24 days before the audit. The age rule fails it from 16 October 2026.

Checker A opened the page with curl, HTTP 200. It is the same news aggregator page as entry 3.

1. Statement: partly confirmed. The rule and the three regulators are confirmed: "the People's Bank of China, the China Financial Supervisory Administration, and the China Securities Regulatory Commission jointly issued the 'Administrative Measures on Customer Due Diligence and Retention of Customer Identification Data and Transaction Records of Financial Institutions', which clearly states that from January 1, 2026, for cross-border remittance services, remittance of RMB 5,000 or more in a single transaction of RMB 5,000 or the equivalent of a foreign currency of 1,000 US dollars or more must be verified." The page says "must be verified", not customer identity verification. The structuring sentence has no support; the nearest sentence is "The purpose is to prevent illegal capital flows, not hinder normal cross-border remittance".
2. Numbers: RMB 5,000, 1,000 US dollars, a single transaction and 1 January 2026 are all confirmed.
3. Date: 5 December 2025, earlier than `date_checked`.
4. Scope: cross border remittance services of financial institutions for all customers. Silent on structuring.

Checker B was sent back for this entry after its first report left it out, and then opened the page with curl, HTTP 200, and found an aggregator that cites the measures without linking them.

1. Statement: the start date, the thresholds and the three regulators are confirmed with the same sentences. The word "identity" appears nowhere on the page; it says "must be verified". The structuring sentence is silent: "split", "splitting", "structur", "multiple people" and "other people" each appear zero times in the article text.
2. Numbers: RMB 5,000 per single transaction, 1,000 US dollars and 1 January 2026 are confirmed.
3. Date: "Zhitongcaijing · 12/05/2025 12:01", 5 December 2025. The page announced a future rule and does not show it in force.
4. Scope: cross border remittance in China in general. Silent on students and on splitting.

Verdict: partly supported, and aged. The page confirms the thresholds, the date and the regulators, but it is silent on the sentence that splitting a transfer across people is structuring, and it says the remittance "must be verified" rather than naming customer identity verification. The source is an aggregator, not the regulators' text, and the entry fails the age rule on 16 October 2026.

## 7. cn_atm_cap_005

Source: https://www.safe.gov.cn/en/2017/1230/1397.html

`checked_by` is "S" and `second_check_by` is empty. `date_checked` is 15 September 2026, 24 days before the audit. The age rule fails it from 16 October 2026.

Checker A's first curl with a short user agent returned HTTP 000 and an empty body; a retry with a full browser user agent returned HTTP 200. It is the State Administration of Foreign Exchange's English translation, which says "The English translation may only be used as a reference. In case a different interpretation of the translated information contained in this website arises, the original Chinese shall prevail."

1. Statement: confirmed. "the sum of withdrawals using the bank cards under the name of the individual (including supplementary cards) shall not exceed the equivalent of RMB 100,000 in every civil year." "The RMB card will continue to be subject to the ceiling of the equivalent of RMB 10,000 per card per day". "In case of overseas cash withdrawals in excess of the annual quota, the individuals will not be allowed to withdraw cash overseas with the domestic bank cards in the current and second years." "This Circular shall take effect as of January 1, 2018." A reads "current and second years" as the rest of that year and the following year, and notes the page says "domestic bank cards".
2. Numbers: 100,000 yuan per civil year, 10,000 yuan per card per day and 1 January 2018 are confirmed.
3. Date: "Dispatch date: 2017-12-30", earlier than `date_checked`. No update mark.
4. Scope: confirmed for individuals withdrawing cash overseas with Chinese bank cards.

Checker B opened the page with curl, HTTP 200, the same regulator translation.

1. Statement: confirmed by the same four sentences, with the same reading of "current and second years".
2. Numbers: 100,000, 10,000 and 1 January 2018 are confirmed with the same units.
3. Date: "Dispatch date: 2017-12-30", signed 29 December 2017. Earlier than `date_checked`.
4. Scope: confirmed.

Verdict: agreement, and aged. Both checkers note that "the following year" is a reading of the translation's "current and second years" and that the page cannot show the rule is still in force. The entry fails the age rule on 16 October 2026.

## 8. cn_wallet_foreign_006

Source: https://english.www.gov.cn/news/202403/01/content_WS65e1dacdc6d0868f4e8e487b.html

`checked_by` is "S" and `second_check_by` is empty. `date_checked` is 15 September 2026, 24 days before the audit. The age rule fails it from 16 October 2026.

Checker A opened the page with curl, HTTP 200. It is a Xinhua news report on the State Council's English portal, not the People's Bank's own notice.

1. Statement: partly confirmed. "China will guide major payment platforms to raise the single transaction limit for overseas travelers using mobile payments from 1,000 U.S. dollars to 5,000 U.S. dollars, a central bank official said Friday." "the central bank will instruct platforms such as Alipay and Tenpay to raise the annual cumulative transaction limit from 10,000 dollars to 50,000 dollars." The page names Alipay and Tenpay, not WeChat Pay, frames the limits for overseas travelers using mobile payments rather than foreign bank cards, and reports a planned change in the future tense.
2. Numbers: 5,000, 50,000, 1,000 and 10,000 US dollars are confirmed.
3. Date: "Updated: March 1, 2024 21:40", earlier than `date_checked`.
4. Scope: partly confirmed. Overseas travelers using mobile payment in China, not students, and no link to foreign bank cards.

Checker B opened the page with curl, HTTP 200, the same report.

1. Statement: the two limits and the date are supported by the same two sentences. "Foreign bank cards linked to Alipay and WeChat Pay" is only partly supported; cards appear only in "improve the efficiency of binding overseas bank cards". "Raised" is not confirmed, because the page says "will guide" and "will instruct".
2. Numbers: all four figures are confirmed.
3. Date: "Updated: March 1, 2024 21:40".
4. Scope: partly confirmed for overseas travelers; not students, not foreign bank cards, and Tenpay rather than WeChat Pay.

Verdict: disagreement, and aged. The entry says foreign bank cards linked to Alipay and WeChat Pay have had their limits raised, while the page reports that the central bank will instruct platforms such as Alipay and Tenpay to raise the limits for overseas travelers using mobile payments; both checkers found it. The entry fails the age rule on 16 October 2026.

## 9. cn_wise_in_007

Source: https://wise.com/help/articles/2955298/guide-to-cny-transfers

`checked_by` is "S" and `second_check_by` is empty. `date_checked` is 15 September 2026, 24 days before the audit. The age rule fails it from 16 October 2026.

Checker A opened the page with curl, HTTP 200. It is Wise's own help centre, and nothing relevant is collapsed.

1. Statement: partly contradicted. The methods are confirmed: "for each of the 4 methods: Alipay, WeChat, UnionPay and bank transfer." The recipient condition is contradicted: "For UnionPay, we support both mainland and non-mainland recipients. The available banks will depend on whether your recipient holds a Mainland Chinese National ID." The page sets no national ID condition for Alipay or Weixin either.
2. Numbers: confirmed. "Sending via Alipay You can send up to 50,000 CNY per transfer" and "Sending via UnionPay You can send up to 33,000 CNY per transaction".
3. Date: no visible date. The page's embedded metadata shows an update on 7 September 2026, earlier than `date_checked`.
4. Scope: confirmed for sending yuan into China with Wise.

Checker B opened the page with curl, HTTP 200.

1. Statement: the methods are confirmed. The recipient condition is contradicted by the same UnionPay sentence, and the page is silent on a national ID for Alipay and Weixin. B adds "You can only send CNY to CIPS member banks."
2. Numbers: 50,000 to Alipay and 33,000 to UnionPay are confirmed, in CNY.
3. Date: no visible date; embedded update of 7 September 2026, earlier than `date_checked`.
4. Scope: confirmed for individual senders paying individual recipients in China.

Verdict: disagreement, and aged. The entry limits the service to recipients with a Chinese national ID, while the page says UnionPay supports both mainland and non mainland recipients and that the ID only decides which banks are available; both checkers found it. The entry fails the age rule on 16 October 2026.

## 10. cn_wise_out_008

Source: https://wise.com/en-cn/blog/alipay-transaction-limit

`checked_by` is "S" and `second_check_by` is empty. `date_checked` is 15 September 2026, 24 days before the audit. The age rule fails it from 16 October 2026.

Checker A opened the page with curl, HTTP 200. It is a Wise blog post, the operator's marketing content, not a help page.

1. Statement: partly confirmed. "Wise allows an expat in China who has a valid tax record issued by the China tax authority to send money abroad from CNY." "Additionally, Wise will apply an overall limit equal to your approximate post-tax income from China." "At present Alipay doesn't support non-mainland Chinese users to send money overseas via its platform." The page does not say "only", and it calls the limit overall, not annual.
2. Numbers: "The limit for a single CNY transfer abroad is 100,000 CNY." A found that Wise's help article on CNY transfers, updated 7 September 2026, gives different figures: "If you're sending CNY from your China bank app, the maximum you can send in one transfer is 300,000 CNY." and "If you are sending CNY from Alipay, the maximum you can send in one transfer is 50,000 CNY."
3. Date: "Lily Li 02.02.24 (updated more than 1 year ago)", 2 February 2024. Earlier than `date_checked`.
4. Scope: confirmed for foreign residents of China sending money out through Wise.

Checker B opened the page with curl, HTTP 200, the same blog.

1. Statement: the tax record, the overall limit tied to income and the Alipay sentence are confirmed with the same quotations. "Only for foreigners" is silent. B found the help article says "If you're from Taiwan, Hong Kong, or Macau you're eligible to send from CNY".
2. Numbers: 100,000 CNY is on the page, but the newer help article gives 300,000 by bank app and 50,000 by Alipay.
3. Date: 2 February 2024. The page carries a disclaimer that Wise makes no guarantee "that the content in the publication is accurate, complete or up to date."
4. Scope: confirmed for foreign residents sending money out of China.

Verdict: partly supported, and aged. The blog confirms the tax record, the 100,000 yuan figure, the limit tied to post tax income and the Alipay sentence, but it is silent on "only for foreigners" and on the limit being annual. Both checkers found that Wise's own help article, updated 7 September 2026, gives 300,000 yuan per transfer from a bank app and 50,000 yuan from Alipay, so the figure rests on a February 2024 blog that Wise's current page contradicts. The entry fails the age rule on 16 October 2026.

## 11. cn_boc_anxin_009

Source: https://www.boc.cn/en/pbservice/pb4/201005/t20100520_1323963.html

`checked_by` is "SP" and `second_check_by` is empty. `date_checked` is 8 October 2026, 1 day before the audit. The age rule fails it from 8 November 2026.

Checker A opened the page with curl, HTTP 200. It is Bank of China's own English page.

1. Statement: mostly confirmed. "'An Xin Account' is a SGD saving account similar to current account in China with a passbook and a Bank ATM withdrawal card." "Applicants shal have acquired admission letter of any university (college) of Singapore." "1. Passport 2. ID card or Hukou book (proof of residential address) 3. Enrollment letter (or admission letter) The documents mentioned above shall all be original." "As the account application is approved, you can make remittance by submitting customer reference number as provided by Singapore Branch". The student's own name is implied, not stated. Only listed branches offer the service: "Beijing Branch, Shanghai Branch, Guangdong Branch, Shenzhen Branch, Jiangsu Branch, Zhejiang Branch, Shandong Branch, Liaoning Branch, Shenyang Branch, Fujian Branch and Tianjin Branch as well as the designated sub-branches". The entry leaves out the activation in Singapore: "After arriving in Singapore, you will personally bring your passport and student's pass to Bank of China Singapore Branch".
2. Numbers: none in the statement. The document list in `values` matches exactly.
3. Date: no date mark. The URL path points to 20 May 2010 and the page holds "Promotion Program 2010 From now on till December 31, 2010". Earlier than `date_checked`, but about sixteen years old.
4. Scope: confirmed for Chinese students going to Singapore.

Checker B opened the page with curl, HTTP 200.

1. Statement: the account, the eligibility, the original documents and the reference number are confirmed with the same quotations. "In the student's own name" is silent. B quotes the same branch list and the same activation step.
2. Numbers: the document list in `values` matches exactly.
3. Date: no date mark; the URL and the 2010 promotion point to May 2010.
4. Scope: confirmed.

Verdict: partly supported. The page confirms the account, the eligibility, the three original documents and the reference number, but it is silent on the account being in the student's own name, it offers the service only at listed branches rather than at any branch in China, and the entry leaves out that the account must be activated in person in Singapore. The page dates from 2010 and cannot show the service is still offered.

## 12. in_upi_paynow_purpose_001

Source: https://www.rbi.org.in/commonman/english/scripts/FAQs.aspx?Id=3415

`checked_by` is "SP" and `second_check_by` is empty. `date_checked` is 8 October 2026, 1 day before the audit. The age rule fails it from 8 November 2026.

Checker A opened the page with curl, HTTP 200. It is the Reserve Bank of India's FAQ page, with every answer in plain text.

1. Statement: confirmed. "Presently, only Person to Person (P2P) remittances for the purposes of “Maintenance of Relatives Abroad” & “Gift” are allowed." "In the UPI-PayNow linkage transactions, only person to person (P2P) remittances towards the purpose of “Maintenance of Relatives Abroad” & “Gift” under the Liberalised Remittance Scheme (LRS) are allowed, and the prescribed LRS limits would be applicable."
2. Numbers: none. Both purposes match.
3. Date: "Display Date: 21/02/2023", earlier than `date_checked`. The page says "Presently".
4. Scope: confirmed for the India and Singapore linkage. A notes that only a few Indian banks take part.

Checker B opened the page with curl, HTTP 200.

1. Statement: confirmed by the same two answers.
2. Numbers: none; both purposes match.
3. Date: "Date: 21/02/2023", earlier than `date_checked`, with no later update.
4. Scope: confirmed. "Account-holders of the participating banks and financial institutions in India and Singapore can do the cross-border remittance transactions through the UPI-PayNow linkage."

Verdict: agreement. Both checkers note the page is dated 21 February 2023 and says "Presently", so it cannot show the rule still holds.

## 13. in_upi_paynow_cap_002

Source: https://www.rbi.org.in/commonman/english/scripts/FAQs.aspx?Id=3415

`checked_by` is "SP" and `second_check_by` is empty. `date_checked` is 8 October 2026, 1 day before the audit. The age rule fails it from 8 November 2026.

Checker A opened the same RBI page with curl, HTTP 200.

1. Statement: confirmed. "There is a daily transaction limit of ₹60,000 in a day (equivalent to around SGD 1,000) for undertaking cross-border remittance transactions through the UPI-PayNow linkage."
2. Numbers: 60,000 rupees per day and around 1,000 Singapore dollars are confirmed.
3. Date: "Display Date: 21/02/2023", earlier than `date_checked`.
4. Scope: confirmed.

Checker B opened the same page with curl, HTTP 200.

1. Statement: confirmed by the same sentence.
2. Numbers: 60,000 rupees in a day and around 1,000 Singapore dollars are confirmed.
3. Date: 21 February 2023, earlier than `date_checked`.
4. Scope: confirmed for the linkage; the page does not say whether the cap differs by direction.

Verdict: agreement. Both checkers note the page is from February 2023.

## 14. wise_docs_channel_001

Source: https://wise.com/help/articles/2949804

`checked_by` is "CC" and `second_check_by` is empty. `date_checked` is 8 October 2026, 1 day before the audit. The age rule fails it from 8 November 2026.

Checker A opened the page with curl, HTTP 200, after a redirect to the article titled how do I verify my address. It is Wise's own help centre.

1. Statement: confirmed. "We'll ask you to upload a high-quality photo or scan of a document." "You can check your verification status at any time by going to the Verification tab in your account settings."
2. Numbers: none in the statement.
3. Date: no visible date; embedded update of 7 September 2026, earlier than `date_checked`.
4. Scope: confirmed for verifying an address worldwide. A notes that the page covers proof of address only, and that the Verification tab is where status is checked, not where documents are collected.

Checker B opened the page with curl, HTTP 200, after the same redirect.

1. Statement: confirmed by the same two sentences.
2. Numbers: none in the statement.
3. Date: no visible date; embedded update of 7 September 2026.
4. Scope: confirmed for all Wise users.

Verdict: agreement. The first checker is recorded as CC, a placeholder.

## 15. wise_docs_impersonation_002

Source: https://wise.com/sg/blog/impersonation-scams

`checked_by` is "CC" and `second_check_by` is empty. `date_checked` is 8 October 2026, 1 day before the audit. The age rule fails it from 8 November 2026.

Checker A opened the page with curl, HTTP 200. It is a Wise Singapore blog post.

1. Statement: confirmed. "Wise will never: Ask for your password Ask for your login details over a phone call Send clickable links asking you to make payments or provide personal information Pressure you to act immediately". "Contact Wise directly through official channels using the Wise website or app." "If a message claims to be from Wise and includes any of the above, it is likely a scam."
2. Numbers: none in the statement.
3. Date: "Michelle Alyssa 03.02.26", 3 February 2026, earlier than `date_checked`.
4. Scope: confirmed for Wise customers.

Checker B opened the page with curl, HTTP 200.

1. Statement: confirmed by the same three sentences.
2. Numbers: none in the statement.
3. Date: 3 February 2026.
4. Scope: confirmed. The page carries a disclaimer that its content may not be accurate or up to date.

Verdict: agreement. The first checker is recorded as CC, a placeholder, and the source is a blog.

## 16. sg_cash_pickup_001

Source: https://www.westernunion.com/sg/en/receive-money.html

`checked_by` is "SP" and `second_check_by` is empty. `date_checked` is 8 October 2026, 1 day before the audit. The age rule fails it from 8 November 2026.

Checker A opened the page with curl, HTTP 200. It is Western Union Singapore's own page. The steps sit in a Cash pickup tab that is open by default.

1. Statement: confirmed. "Receive money your way in Singapore". "Visit a Western Union agent location. Provide your sender's details, including the Money Transfer Control Number (MTCN). Show a government-issued photo ID. Get your money once your details have been verified."
2. Numbers: none in the statement.
3. Date: no visible date. The HTTP Last-Modified header is 1 September 2026, earlier than `date_checked`.
4. Scope: confirmed for receivers in Singapore.

Checker B opened the page with curl, HTTP 200.

1. Statement: confirmed by the same steps, in the Cash pickup tab that is active by default.
2. Numbers: none.
3. Date: Last-Modified 1 September 2026.
4. Scope: confirmed.

Verdict: agreement.

## 17. sg_card_replacement_002

Source: https://wise.com/help/articles/2935787/how-do-i-replace-or-cancel-my-wise-card

`checked_by` is "SP" and `second_check_by` is empty. `date_checked` is 8 October 2026, 1 day before the audit. The age rule fails it from 8 November 2026.

Checker A opened the page with curl, HTTP 200. It is Wise's own help centre, and the table is not collapsed.

1. Statement: confirmed. "Delivery times depend on your region and are estimates in working days. Working days are Monday to Friday, and don't include weekends or public holidays." The table row reads "Singapore 3 days".
2. Numbers: 3 working days for Singapore is confirmed.
3. Date: no visible date; embedded update of 4 May 2026, earlier than `date_checked`.
4. Scope: confirmed for replacement Wise cards sent to Singapore.

Checker B opened the page with curl, HTTP 200.

1. Statement: confirmed by the same sentences and the same row.
2. Numbers: 3 working days is confirmed.
3. Date: embedded update of 4 May 2026.
4. Scope: confirmed.

Verdict: agreement.

## 18. sg_nus_fee_payment_003

Source: https://www.nus.edu.sg/finance/students/student-finance-matters/payments/other-payment-modes

`checked_by` is "SP" and `second_check_by` is empty. `date_checked` is 8 October 2026, 1 day before the audit. The age rule fails it from 8 November 2026.

Checker A could not open the page. Curl returned HTTP 200 with a 949 byte Imperva Incapsula challenge reading "Request unsuccessful. Incapsula incident ID: 936000360135781054-64199148272355630", twice. A direct fetch returned no content: "the web page content provided is empty." All four points are unreachable.

Checker B could not open the live page either. Curl returned the same challenge, "Request unsuccessful. Incapsula incident ID: 936000360135781054-44426600605288749", and a direct fetch of the URL with and without a trailing slash returned an empty page. B then read the newest archived copy, captured 20 August 2026 and modified 22 July 2026, which is not the live page. In that copy, inside collapsed FAQ sections, "We strongly recommend that international students make fee payments via Flywire or Convera through NUS FastPay." and "For e-wallet payments and international wire transfer, please allow up to 1-2 business day for the payment to be reflected in EduRec." The copy holds no sentence on Convera GlobalPay, on a family member or third party paying through it, on KYC, on authentication, on relationship documents, or on 2 to 3 business days.

Verdict: unreachable. Neither checker could open the live page, which returned an Incapsula bot challenge. The archived copy of 20 August 2026 supports only the recommendation and the 1 to 2 business days for Flywire, so the rest of the statement rests on the live page that SP read in a browser on 8 October 2026.

## Summary

| Verdict | Count | Entries |
| --- | --- | --- |
| Agreement | 8 | `br_pix_keys_002`, `cn_atm_cap_005`, `in_upi_paynow_purpose_001`, `in_upi_paynow_cap_002`, `wise_docs_channel_001`, `wise_docs_impersonation_002`, `sg_cash_pickup_001`, `sg_card_replacement_002` |
| Disagreement | 5 | `br_pix_instant_001`, `cn_fx_quota_001`, `cn_edu_docs_003`, `cn_wallet_foreign_006`, `cn_wise_in_007` |
| Partly supported | 4 | `cn_edu_remit_002`, `cn_cdd_004`, `cn_wise_out_008`, `cn_boc_anxin_009` |
| Unreachable | 1 | `sg_nus_fee_payment_003` |
| Aged, beside another verdict | 8 | `cn_fx_quota_001`, `cn_edu_remit_002`, `cn_edu_docs_003`, `cn_cdd_004`, `cn_atm_cap_005`, `cn_wallet_foreign_006`, `cn_wise_in_007`, `cn_wise_out_008`, all failing on 16 October 2026 |

The 18 entries take 18 main verdicts, and 8 of them are also aged. No entry has a second check: `second_check_by` is empty on all 18, so by the README's second rule none of them may yet appear in a demo.

### Sources that are a news aggregator or a blog

1. `cn_fx_quota_001` cites a Webull news page that reposts a Zhitongcaijing article of 5 December 2025.
2. `cn_cdd_004` cites the same Webull page.
3. `cn_wise_out_008` cites a Wise blog post of 2 February 2024, which Wise's own help article now contradicts.
4. `wise_docs_impersonation_002` cites a Wise Singapore blog post of 3 February 2026. It is the operator's own blog, and both checkers found it accurate.

`cn_wallet_foreign_006` is not on this list because it sits on a government portal, but its page is a Xinhua news report of a press briefing, not the People's Bank's own notice.

### Entries whose first checker is a placeholder

1. `wise_docs_channel_001`, `checked_by` "CC".
2. `wise_docs_impersonation_002`, `checked_by` "CC".

The README says CC means Claude Code checked the entry and that a person replaces it with their initials. The eight China entries checked on 15 September 2026 carry "S", a single letter where the README asks for initials; it is not a placeholder by the README's definition, but lane B should confirm whose initials it stands for.

## For lane B

Every entry needs a second checker's initials in `second_check_by`. Beyond that, the work for each entry is as follows, in file order.

1. `br_pix_instant_001`: correct the statement. Its second sentence should say that participants are financial institutions, payment institutions and government entities that adhere to the Pix Regulation, and that participation is mandatory for authorized institutions with more than half a million active customer accounts. Then confirm and add initials.
2. `br_pix_keys_002`: confirm and add initials.
3. `cn_fx_quota_001`: replace the source with a primary page from the State Administration of Foreign Exchange, remove the claim of January 2026 reporting, and find primary support for study abroad as a permitted purpose or remove that sentence. Check it again before 16 October 2026.
4. `cn_edu_remit_002`: find a page that covers the right scope, since HSBC's page serves only certain HSBC customers paying institutions in the US, UK, Canada, Australia and Hong Kong. If the entry keeps this page, correct the statement to name HSBC China and its customer tiers, and drop the claims on the institution's account and the daily limit unless the page ties them to the path outside the quota. Check it again before 16 October 2026.
5. `cn_edu_docs_003`: correct the statement to say documents are uploaded through HSBC mobile banking as photos or scans of the originals, that photos or scans of copies are refused, and that this is HSBC's own list. Check it again before 16 October 2026.
6. `cn_cdd_004`: replace the source with the text of the joint measures from the People's Bank of China, and either find a primary page that supports the structuring sentence or remove it. Check it again before 16 October 2026.
7. `cn_atm_cap_005`: confirm and add initials before 16 October 2026.
8. `cn_wallet_foreign_006`: replace the source with the People's Bank's own notice or the wallet operators' pages that state the limits in force for foreign cards, or correct the statement to say the central bank said on 1 March 2024 it would instruct platforms such as Alipay and Tenpay to raise the limits for overseas travelers. Check it again before 16 October 2026.
9. `cn_wise_in_007`: correct the statement and the `recipient_condition` value, because UnionPay serves recipients with or without a mainland Chinese national ID and the ID only decides which banks are available. Check it again before 16 October 2026.
10. `cn_wise_out_008`: replace the source with Wise's help article on CNY transfers and correct the per transfer figures to the ones it gives, 300,000 yuan from a China bank app and 50,000 yuan from Alipay, along with who is eligible. Check it again before 16 October 2026.
11. `cn_boc_anxin_009`: find a current Bank of China page that shows the An Xin account is still offered, since the page on file dates from 2010. Correct the statement to name the listed branches instead of any branch, and to say the account must be activated in person at the Singapore Branch, or drop the words about the student's own name if no page states them.
12. `in_upi_paynow_purpose_001`: confirm and add initials, and look for a newer RBI or NPCI page, since the FAQ dates from 21 February 2023.
13. `in_upi_paynow_cap_002`: confirm and add initials, with the same search for a newer page.
14. `wise_docs_channel_001`: confirm and add initials in place of CC.
15. `wise_docs_impersonation_002`: confirm and add initials in place of CC.
16. `sg_cash_pickup_001`: confirm and add initials.
17. `sg_card_replacement_002`: confirm and add initials.
18. `sg_nus_fee_payment_003`: confirm in a browser and add initials. If the live page no longer holds the sentences on Convera GlobalPay, KYC, relationship documents and 2 to 3 business days, which the archived copy of 20 August 2026 lacks, correct the statement to the sentences the page does hold.
