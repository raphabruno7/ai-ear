# Eval run 20260909-115057

stt: Deepgram Nova-3    name seeding: Nova-3 keyterms (15 names)

| model | kind | n | exact | phonetic | mean WER | mean lev |
|---|---|--:|--:|--:|--:|--:|
| bedrock-haiku | name | 15 | 60% | 67% | 0.367 | 0.161 |
| bedrock-haiku | email | 10 | 30% | 30% | 0.700 | 0.078 |
| gemini-flash | name | 15 | 60% | 80% | 0.278 | 0.103 |
| gemini-flash | email | 10 | 30% | 30% | 0.700 | 0.165 |

## STT is the bottleneck

Samples **every** model got wrong — because Deepgram Nova-3 mis-heard the audio and both models faithfully returned what they were given:

| sample | expected | Deepgram Nova-3 heard | bedrock-haiku | gemini-flash |
|---|---|---|---|---|
| e02 | `g.weisz2@outlook.com` | "G.wys2@outlook.com" | `G.wys2@outlook.com` | `g.wys2@outlook.com` |
| e03 | `s_gallagher@yahoo.co.uk` | "Sgallagheryahoo dot co dot uk" | `s.gallagher@yahoo.co.uk` | `sgallagher@yahoo.co.uk` |
| e04 | `priya.raj@protonmail.com` | "Priya dot rajatprotonmail dot com" | `priya.rajat@protonmail.com` | `priya.rajat@protonmail.com` |
| e05 | `hoa.nguyen87@gmail.com` | "Hoa.ven87@gmail.com" | `hoa.ven87@gmail.com` | `hoa.ven87@gmail.com` |
| e06 | `sean.maccarthy@icloud.com` | "Sean.mccarthy@icloud.com" | `Sean.mccarthy@icloud.com` | `sean.mccarthy@icloud.com` |
| e09 | `k.hepburn.clarke@nhs.net` | "K. Hepburn. Clarknhs dot net" | `k.hepburn@clarknhs.net` | `` |
| e10 | `xzhang@stanford.edu` | "Xjongstanford dot edu" | `xjong@stanford.edu` | `xjong@stanford.edu` |
| n04 | `Aoife Ní Bhraonáin` | "My name is Efani Bhraonavan." | `Efani Bhraonavan` | `Efani Bhraonavan` |
| n12 | `Seán Mac Cárthaigh` | "Sean Mac Cave" | `Sean MacCave` | `Sean Mac Cave` |
| n14 | `Björn Andersson` | "Andersson, with an Umlaut over the o." | `` | `Anderssön` |

## Misses

- `bedrock-haiku` n04 — expected `Aoife Ní Bhraonáin`, got `Efani Bhraonavan`
- `gemini-flash` n04 — expected `Aoife Ní Bhraonáin`, got `Efani Bhraonavan`
- `bedrock-haiku` n08 — expected `Zoë Featherstonehaugh`, got `Zo Featherstone­haugh`
- `bedrock-haiku` n12 — expected `Seán Mac Cárthaigh`, got `Sean MacCave`
- `gemini-flash` n12 — expected `Seán Mac Cárthaigh`, got `Sean Mac Cave`
- `bedrock-haiku` n14 — expected `Björn Andersson`, got ``
- `gemini-flash` n14 — expected `Björn Andersson`, got `Anderssön`
- `bedrock-haiku` n15 — expected `Charlotte Cholmondeley`, got `Charlotte Chumley`
- `bedrock-haiku` e02 — expected `g.weisz2@outlook.com`, got `G.wys2@outlook.com`
- `gemini-flash` e02 — expected `g.weisz2@outlook.com`, got `g.wys2@outlook.com`
- `bedrock-haiku` e03 — expected `s_gallagher@yahoo.co.uk`, got `s.gallagher@yahoo.co.uk`
- `gemini-flash` e03 — expected `s_gallagher@yahoo.co.uk`, got `sgallagher@yahoo.co.uk`
- `bedrock-haiku` e04 — expected `priya.raj@protonmail.com`, got `priya.rajat@protonmail.com`
- `gemini-flash` e04 — expected `priya.raj@protonmail.com`, got `priya.rajat@protonmail.com`
- `bedrock-haiku` e05 — expected `hoa.nguyen87@gmail.com`, got `hoa.ven87@gmail.com`
- `gemini-flash` e05 — expected `hoa.nguyen87@gmail.com`, got `hoa.ven87@gmail.com`
- `bedrock-haiku` e06 — expected `sean.maccarthy@icloud.com`, got `Sean.mccarthy@icloud.com`
- `gemini-flash` e06 — expected `sean.maccarthy@icloud.com`, got `sean.mccarthy@icloud.com`
- `bedrock-haiku` e09 — expected `k.hepburn.clarke@nhs.net`, got `k.hepburn@clarknhs.net`
- `gemini-flash` e09 — expected `k.hepburn.clarke@nhs.net`, got ``
- `bedrock-haiku` e10 — expected `xzhang@stanford.edu`, got `xjong@stanford.edu`
- `gemini-flash` e10 — expected `xzhang@stanford.edu`, got `xjong@stanford.edu`
