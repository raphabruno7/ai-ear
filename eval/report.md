# Eval run 20260901-225332

| model | kind | n | exact | phonetic | mean WER | mean lev |
|---|---|--:|--:|--:|--:|--:|
| gemini-flash | name | 15 | 47% | 67% | 0.378 | 0.163 |
| gemini-flash | email | 10 | 30% | 30% | 0.700 | 0.092 |

## Misses

- `gemini-flash` n04 — expected `Aoife Ní Bhraonáin`, got `Aoife Ibra Oman`
- `gemini-flash` n05 — expected `Nguyen Thi Hoa`, got `Nguyen`
- `gemini-flash` n07 — expected `Michał Wojciechowski`, got `Mitchell Wozkowski`
- `gemini-flash` n11 — expected `Xiuying Zhang`, got `Xu Ying Zhang`
- `gemini-flash` n12 — expected `Seán Mac Cárthaigh`, got `Sean McCarvey`
- `gemini-flash` e02 — expected `g.weisz2@outlook.com`, got `g.w2@outlook.com`
- `gemini-flash` e04 — expected `priya.raj@protonmail.com`, got `priya.roger@protonmail.com`
- `gemini-flash` e05 — expected `hoa.nguyen87@gmail.com`, got `hua.wen87@mail.com`
- `gemini-flash` e06 — expected `sean.maccarthy@icloud.com`, got `sean.mccarthy@icloud.com`
- `gemini-flash` e08 — expected `deshawn.j@gmail.com`, got `deshatwn.j@gmail.com`
- `gemini-flash` e09 — expected `k.hepburn.clarke@nhs.net`, got `k.hepburn.clark@nhs.net`
- `gemini-flash` e10 — expected `xzhang@stanford.edu`, got `xjong@stanford.edu`
