# Eval run 20260907-214252

custom vocabulary: call-copilot-en-US

| model | kind | n | exact | phonetic | mean WER | mean lev |
|---|---|--:|--:|--:|--:|--:|
| bedrock-haiku | name | 15 | 33% | 60% | 0.511 | 0.136 |
| bedrock-haiku | email | 10 | 30% | 30% | 0.700 | 0.077 |
| gemini-flash | name | 15 | 53% | 60% | 0.356 | 0.119 |
| gemini-flash | email | 10 | 30% | 30% | 0.700 | 0.077 |

## STT is the bottleneck

Samples **every** model got wrong — because AWS Transcribe mis-heard the audio and both models faithfully returned what they were given:

| sample | expected | Transcribe heard | bedrock-haiku | gemini-flash |
|---|---|---|---|---|
| e02 | `g.weisz2@outlook.com` | "G. Weis2@outlook.com." | `G.Weis2@outlook.com` | `g.weis2@outlook.com` |
| e04 | `priya.raj@protonmail.com` | "Priya. Rogerprotonmail.com." | `priya.roger@protonmail.com` | `priya.roger@protonmail.com` |
| e05 | `hoa.nguyen87@gmail.com` | "Hua.wen87@mail.com." | `Hua.wen87@mail.com` | `hua.wen87@mail.com` |
| e06 | `sean.maccarthy@icloud.com` | "Sean. McCarthy@icloud.com." | `Sean.McCarthy@icloud.com` | `sean.mccarthy@icloud.com` |
| e08 | `deshawn.j@gmail.com` | "DESH at WN.J@gmail.com." | `desh@wn.j@gmail.com` | `desh.wn.j@gmail.com` |
| e09 | `k.hepburn.clarke@nhs.net` | "K. Hepburn.Clark@ NHS.net." | `k.hepburn.clark@nhs.net` | `k.hepburn.clark@nhs.net` |
| e10 | `xzhang@stanford.edu` | "Xjong at stanford.edu." | `xjong@stanford.edu` | `xjong@stanford.edu` |
| n04 | `Aoife Ní Bhraonáin` | "My name is Aife Ibra Oman." | `Aife Ibra Oman` | `Aife Ibra Oman` |
| n05 | `Nguyen Thi Hoa` | "Nguyen Ti Hoa. The family name is Nguyen, N G U Y E N." | `Nguyen Ti Hoa` | `Nguyen Ti Hoa` |
| n06 | `Priya Rajagopalan` | "This is Pre by Raja Gopalan." | `Pre Raja Gopalan` | `Preeby Rajagopalan` |
| n07 | `Michał Wojciechowski` | "Mitchell Wojciechowski, that's a Polish name." | `Mitchell Wojciechowski` | `Mitchell Wojciechowski` |
| n11 | `Xiuying Zhang` | "My name is Xu Ying Zhang." | `Xu Ying Zhang` | `Xu Ying Zhang` |
| n12 | `Seán Mac Cárthaigh` | "Sean McCarvey" | `Sean McCarvey` | `Sean McCarvey` |

## Misses

- `bedrock-haiku` n04 — expected `Aoife Ní Bhraonáin`, got `Aife Ibra Oman`
- `gemini-flash` n04 — expected `Aoife Ní Bhraonáin`, got `Aife Ibra Oman`
- `bedrock-haiku` n05 — expected `Nguyen Thi Hoa`, got `Nguyen Ti Hoa`
- `gemini-flash` n05 — expected `Nguyen Thi Hoa`, got `Nguyen Ti Hoa`
- `bedrock-haiku` n06 — expected `Priya Rajagopalan`, got `Pre Raja Gopalan`
- `gemini-flash` n06 — expected `Priya Rajagopalan`, got `Preeby Rajagopalan`
- `bedrock-haiku` n07 — expected `Michał Wojciechowski`, got `Mitchell Wojciechowski`
- `gemini-flash` n07 — expected `Michał Wojciechowski`, got `Mitchell Wojciechowski`
- `bedrock-haiku` n11 — expected `Xiuying Zhang`, got `Xu Ying Zhang`
- `gemini-flash` n11 — expected `Xiuying Zhang`, got `Xu Ying Zhang`
- `bedrock-haiku` n12 — expected `Seán Mac Cárthaigh`, got `Sean McCarvey`
- `gemini-flash` n12 — expected `Seán Mac Cárthaigh`, got `Sean McCarvey`
- `bedrock-haiku` e02 — expected `g.weisz2@outlook.com`, got `G.Weis2@outlook.com`
- `gemini-flash` e02 — expected `g.weisz2@outlook.com`, got `g.weis2@outlook.com`
- `bedrock-haiku` e04 — expected `priya.raj@protonmail.com`, got `priya.roger@protonmail.com`
- `gemini-flash` e04 — expected `priya.raj@protonmail.com`, got `priya.roger@protonmail.com`
- `bedrock-haiku` e05 — expected `hoa.nguyen87@gmail.com`, got `Hua.wen87@mail.com`
- `gemini-flash` e05 — expected `hoa.nguyen87@gmail.com`, got `hua.wen87@mail.com`
- `bedrock-haiku` e06 — expected `sean.maccarthy@icloud.com`, got `Sean.McCarthy@icloud.com`
- `gemini-flash` e06 — expected `sean.maccarthy@icloud.com`, got `sean.mccarthy@icloud.com`
- `bedrock-haiku` e08 — expected `deshawn.j@gmail.com`, got `desh@wn.j@gmail.com`
- `gemini-flash` e08 — expected `deshawn.j@gmail.com`, got `desh.wn.j@gmail.com`
- `bedrock-haiku` e09 — expected `k.hepburn.clarke@nhs.net`, got `k.hepburn.clark@nhs.net`
- `gemini-flash` e09 — expected `k.hepburn.clarke@nhs.net`, got `k.hepburn.clark@nhs.net`
- `bedrock-haiku` e10 — expected `xzhang@stanford.edu`, got `xjong@stanford.edu`
- `gemini-flash` e10 — expected `xzhang@stanford.edu`, got `xjong@stanford.edu`
