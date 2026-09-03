# Eval run 20260903-130653

| model | kind | n | exact | phonetic | mean WER | mean lev |
|---|---|--:|--:|--:|--:|--:|
| bedrock-haiku | name | 15 | 40% | 60% | 0.589 | 0.170 |
| bedrock-haiku | email | 10 | 30% | 30% | 0.700 | 0.092 |
| gemini-flash | name | 15 | 40% | 60% | 0.444 | 0.157 |
| gemini-flash | email | 10 | 30% | 30% | 0.700 | 0.092 |

## STT is the bottleneck

Samples **every** model got wrong — because AWS Transcribe mis-heard the audio and both models faithfully returned what they were given:

| sample | expected | Transcribe heard | bedrock-haiku | gemini-flash |
|---|---|---|---|---|
| e02 | `g.weisz2@outlook.com` | "G.W2@outlook.com." | `G.W2@outlook.com` | `g.w2@outlook.com` |
| e04 | `priya.raj@protonmail.com` | "Priya. Rogerprotonmail.com." | `priya.roger@protonmail.com` | `priya.roger@protonmail.com` |
| e05 | `hoa.nguyen87@gmail.com` | "Hua.wen87@mail.com." | `Hua.wen87@mail.com` | `hua.wen87@mail.com` |
| e06 | `sean.maccarthy@icloud.com` | "Sean. McCarthy@iCloud.com." | `Sean.McCarthy@iCloud.com` | `sean.mccarthy@icloud.com` |
| e08 | `deshawn.j@gmail.com` | "DESH at WN.J@gmail.com." | `desh@wn.j@gmail.com` | `desh.wn.j@gmail.com` |
| e09 | `k.hepburn.clarke@nhs.net` | "K. Hepburn.Clark@ NHS.net." | `k.hepburn.clark@nhs.net` | `k.hepburn.clark@nhs.net` |
| e10 | `xzhang@stanford.edu` | "Xjong at stanford.edu." | `xjong@stanford.edu` | `xjong@stanford.edu` |
| n04 | `Aoife Ní Bhraonáin` | "My name is Aoife Ibra Oman." | `Aoife Ibra Oman` | `Aoife Ibra Oman` |
| n05 | `Nguyen Thi Hoa` | "Nguyenihoa. The family name is Nguyen, N G U Y E N." | `Nguyenihoa` | `Nguyen Ihoa` |
| n06 | `Priya Rajagopalan` | "This is Pre by Raja Gopalan." | `Pre Raja Gopalan` | `Preeby Rajagopalan` |
| n07 | `Michał Wojciechowski` | "Mitchell Wozkowski, that's a Polish name." | `Mitchell Wozkowski` | `Mitchell Wozkowski` |
| n11 | `Xiuying Zhang` | "My name is Xu Ying Zhang." | `Xu Ying Zhang` | `Xu Ying Zhang` |
| n12 | `Seán Mac Cárthaigh` | "Sean McCarvey" | `Sean McCarvey` | `Sean McCarvey` |

## Misses

- `bedrock-haiku` n04 — expected `Aoife Ní Bhraonáin`, got `Aoife Ibra Oman`
- `gemini-flash` n04 — expected `Aoife Ní Bhraonáin`, got `Aoife Ibra Oman`
- `bedrock-haiku` n05 — expected `Nguyen Thi Hoa`, got `Nguyenihoa`
- `gemini-flash` n05 — expected `Nguyen Thi Hoa`, got `Nguyen Ihoa`
- `bedrock-haiku` n06 — expected `Priya Rajagopalan`, got `Pre Raja Gopalan`
- `gemini-flash` n06 — expected `Priya Rajagopalan`, got `Preeby Rajagopalan`
- `bedrock-haiku` n07 — expected `Michał Wojciechowski`, got `Mitchell Wozkowski`
- `gemini-flash` n07 — expected `Michał Wojciechowski`, got `Mitchell Wozkowski`
- `bedrock-haiku` n11 — expected `Xiuying Zhang`, got `Xu Ying Zhang`
- `gemini-flash` n11 — expected `Xiuying Zhang`, got `Xu Ying Zhang`
- `bedrock-haiku` n12 — expected `Seán Mac Cárthaigh`, got `Sean McCarvey`
- `gemini-flash` n12 — expected `Seán Mac Cárthaigh`, got `Sean McCarvey`
- `bedrock-haiku` e02 — expected `g.weisz2@outlook.com`, got `G.W2@outlook.com`
- `gemini-flash` e02 — expected `g.weisz2@outlook.com`, got `g.w2@outlook.com`
- `bedrock-haiku` e04 — expected `priya.raj@protonmail.com`, got `priya.roger@protonmail.com`
- `gemini-flash` e04 — expected `priya.raj@protonmail.com`, got `priya.roger@protonmail.com`
- `bedrock-haiku` e05 — expected `hoa.nguyen87@gmail.com`, got `Hua.wen87@mail.com`
- `gemini-flash` e05 — expected `hoa.nguyen87@gmail.com`, got `hua.wen87@mail.com`
- `bedrock-haiku` e06 — expected `sean.maccarthy@icloud.com`, got `Sean.McCarthy@iCloud.com`
- `gemini-flash` e06 — expected `sean.maccarthy@icloud.com`, got `sean.mccarthy@icloud.com`
- `bedrock-haiku` e08 — expected `deshawn.j@gmail.com`, got `desh@wn.j@gmail.com`
- `gemini-flash` e08 — expected `deshawn.j@gmail.com`, got `desh.wn.j@gmail.com`
- `bedrock-haiku` e09 — expected `k.hepburn.clarke@nhs.net`, got `k.hepburn.clark@nhs.net`
- `gemini-flash` e09 — expected `k.hepburn.clarke@nhs.net`, got `k.hepburn.clark@nhs.net`
- `bedrock-haiku` e10 — expected `xzhang@stanford.edu`, got `xjong@stanford.edu`
- `gemini-flash` e10 — expected `xzhang@stanford.edu`, got `xjong@stanford.edu`
