# Eval run 20260909-130016

stt: AWS Transcribe    name seeding: custom vocabulary call-copilot-en-US
noise: clean    apm: off

| model | kind | n | exact | phonetic | mean WER | mean lev |
|---|---|--:|--:|--:|--:|--:|
| bedrock-haiku | name | 15 | 53% | 67% | 0.333 | 0.108 |
| bedrock-haiku | email | 10 | 20% | 20% | 0.800 | 0.108 |
| gemini-flash | name | 15 | 53% | 60% | 0.367 | 0.167 |
| gemini-flash | email | 10 | 50% | 50% | 0.500 | 0.057 |

## STT is the bottleneck

Samples **every** model got wrong — because AWS Transcribe mis-heard the audio and both models faithfully returned what they were given:

| sample | expected | AWS Transcribe heard | bedrock-haiku | gemini-flash |
|---|---|---|---|---|
| e02 | `g.weisz2@outlook.com` | "G. Weis2@outlook.com." | `G.Weis2@outlook.com` | `g.weis2@outlook.com` |
| e04 | `priya.raj@protonmail.com` | "Priya. Rogerprotonmail.com." | `priya.roger@protonmail.com` | `priya.roger@protonmail.com` |
| e05 | `hoa.nguyen87@gmail.com` | "Hua.wen87@mail.com." | `Hua.wen87@mail.com` | `hua.wen87@mail.com` |
| e06 | `sean.maccarthy@icloud.com` | "Sean. McCarthy@icloud.com." | `Sean.McCarthy@icloud.com` | `sean.mccarthy@icloud.com` |
| e08 | `deshawn.j@gmail.com` | "DESH at WN.J@gmail.com." | `desh@wn.j@gmail.com` | `desh.wn.j@gmail.com` |
| n04 | `Aoife Ní Bhraonáin` | "My name is Aoife Ireoneman." | `Aoife Ireoneman` | `Aoife Ireoneman` |
| n05 | `Nguyen Thi Hoa` | "Nguyen Ti Hoa. The family name is Nguyen, N G U Y E N." | `Nguyen Ti Hoa` | `Nguyen Ti Hoa` |
| n07 | `Michał Wojciechowski` | "Mitchell Wojciechowski, that's a Polish name." | `Mitchell Wojciechowski` | `Mitchell Wojciechowski` |
| n11 | `Xiuying Zhang` | "My name is Xu Ying Zhang." | `Xu Ying Zhang` | `Xu Ying Zhang` |
| n12 | `Seán Mac Cárthaigh` | "Sean Maccafey" | `Sean Maccaffey` | `Sean Maccafey` |

## Misses

- `bedrock-haiku` n04 — expected `Aoife Ní Bhraonáin`, got `Aoife Ireoneman`
- `gemini-flash` n04 — expected `Aoife Ní Bhraonáin`, got `Aoife Ireoneman`
- `bedrock-haiku` n05 — expected `Nguyen Thi Hoa`, got `Nguyen Ti Hoa`
- `gemini-flash` n05 — expected `Nguyen Thi Hoa`, got `Nguyen Ti Hoa`
- `bedrock-haiku` n07 — expected `Michał Wojciechowski`, got `Mitchell Wojciechowski`
- `gemini-flash` n07 — expected `Michał Wojciechowski`, got `Mitchell Wojciechowski`
- `gemini-flash` n09 — expected `DeShawn Jackson`, got ``
- `bedrock-haiku` n11 — expected `Xiuying Zhang`, got `Xu Ying Zhang`
- `gemini-flash` n11 — expected `Xiuying Zhang`, got `Xu Ying Zhang`
- `bedrock-haiku` n12 — expected `Seán Mac Cárthaigh`, got `Sean Maccaffey`
- `gemini-flash` n12 — expected `Seán Mac Cárthaigh`, got `Sean Maccafey`
- `bedrock-haiku` e02 — expected `g.weisz2@outlook.com`, got `G.Weis2@outlook.com`
- `gemini-flash` e02 — expected `g.weisz2@outlook.com`, got `g.weis2@outlook.com`
- `bedrock-haiku` e03 — expected `s_gallagher@yahoo.co.uk`, got `s.gallagher@yahoo.co.uk`
- `bedrock-haiku` e04 — expected `priya.raj@protonmail.com`, got `priya.roger@protonmail.com`
- `gemini-flash` e04 — expected `priya.raj@protonmail.com`, got `priya.roger@protonmail.com`
- `bedrock-haiku` e05 — expected `hoa.nguyen87@gmail.com`, got `Hua.wen87@mail.com`
- `gemini-flash` e05 — expected `hoa.nguyen87@gmail.com`, got `hua.wen87@mail.com`
- `bedrock-haiku` e06 — expected `sean.maccarthy@icloud.com`, got `Sean.McCarthy@icloud.com`
- `gemini-flash` e06 — expected `sean.maccarthy@icloud.com`, got `sean.mccarthy@icloud.com`
- `bedrock-haiku` e08 — expected `deshawn.j@gmail.com`, got `desh@wn.j@gmail.com`
- `gemini-flash` e08 — expected `deshawn.j@gmail.com`, got `desh.wn.j@gmail.com`
- `bedrock-haiku` e09 — expected `k.hepburn.clarke@nhs.net`, got `clarke@nhs.net`
- `bedrock-haiku` e10 — expected `xzhang@stanford.edu`, got `x.zhang@stanford.edu`
