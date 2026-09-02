# Eval run 20260902-201020

| model | kind | n | exact | phonetic | mean WER | mean lev |
|---|---|--:|--:|--:|--:|--:|
| bedrock-haiku | name | 15 | 40% | 60% | 0.589 | 0.170 |
| bedrock-haiku | email | 10 | 30% | 30% | 0.700 | 0.092 |
| gemini-flash | name | 15 | 47% | 67% | 0.433 | 0.145 |
| gemini-flash | email | 10 | 30% | 30% | 0.700 | 0.092 |

## Misses

- `bedrock-haiku` n04 — expected `Aoife Ní Bhraonáin`, got `Aoife Ibra Oman`
- `gemini-flash` n04 — expected `Aoife Ní Bhraonáin`, got `Aoife Ibra Oman`
- `bedrock-haiku` n05 — expected `Nguyen Thi Hoa`, got `Nguyenihoa`
- `gemini-flash` n05 — expected `Nguyen Thi Hoa`, got `Nguyen Ihoa`
- `bedrock-haiku` n06 — expected `Priya Rajagopalan`, got `Pre Raja Gopalan`
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
