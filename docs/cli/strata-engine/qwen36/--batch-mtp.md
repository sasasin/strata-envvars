# `strata` / `strata-q36` `--batch-mtp` (Qwen3.6)

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（Qwen3.6 に振り分けられた場合）または `strata-q36` |
| オプション | `--batch-mtp` |
| 別名 | なし |
| 値 | なし。フラグ |

## 役割

Qwen3.6 の `--serve` で、batch slot ごとに MTP block が提案した次 token を、次の main-model decode window で slot の現在 token と一緒に検証します。提案 token が一致すれば、その window から slot は最大 2 token 分進みます。複数 session と MTP draft block が有効な場合だけ動作します。通常の単一要求生成や benchmark の decode を batch MTP に切り替えるオプションではありません（`engine/src/qwen35/q36_engine.cu:4759-4763,4900-4909,5555-5563,5614-5627`）。

## 使い方

```sh
# Qwen3.6 を serve mode で起動し、4 session と MTP 1 draft を使う
strata-q36 --serve --model MODEL.gguf --batch 4 --mtp 1 --batch-mtp
```

`strata --serve --model MODEL.gguf --batch 4 --mtp 1 --batch-mtp` も、model family 判定で Qwen3.6 parser に振り分けられます（`engine/src/program/generate.cpp:3808-3818`）。ここでの `--mtp N` はこの family の GGUF 内 MTP block が提案する draft 数で、draft directory を渡す形式ではありません（`engine/src/qwen35/q36_engine.cu:5373-5379`）。

## 値と既定値

- `--batch-mtp` は値を取りません。parser は見つけると真偽値を `true` にします。繰り返し指定しても同じ設定です（`engine/src/qwen35/q36_engine.cu:5348-5353,5382-5384`）。
- 省略時は無効です。`--batch` の既定は `0` で、engine は session 数を最低 1 に制限します。`--mtp` の既定は `0`、有効範囲は `0..7` です（`engine/src/qwen35/q36_engine.cu:5342-5347,5456-5457,1962-1967`）。
- 有効条件は engine が確保した session 数が 1 より大きく、モデルに MTP があり、`--mtp` の値が 0 より大きいことです。条件を満たさない状態でこのフラグを明示すると、stderr に `--batch-mtp needs --batch N (2 or more) and --mtp N: ignored` と出し、終了せず無効のまま続行します（`engine/src/qwen35/q36_engine.cu:5555-5562`）。
- `STRATA_BATCH_MTP` でも同じ機能を有効化できます。Qwen3.6 parser は値が設定され、文字列が厳密に `0` でなければ有効扱いにします（空文字列も有効扱い）。これも複数 session と MTP draft が必要です（`engine/src/qwen35/q36_engine.cu:5556-5560`）。この環境変数の個別文書は本リポジトリにありません。

## 実行時の動作

- serve の各 window で、active slot 数 `S` に対し `Engine::kVerify - S` 行分の余裕があり、少なくとも1 slot が提案対象なら MTP 付き window を選びます。既定では greedy slot が候補です。`STRATA_Q36_MTP_SAMPLED` が設定されて `0` 以外なら sampled slot も候補になります。余裕または候補がなければ通常の一 token window に進みます（`engine/src/qwen35/q36_engine.cu:4900-4909,4772-4781`）。
- 候補 slot の行は現在 token と MTP proposal の最大2行です。main model の選択が proposal と一致し、EOS・slot 停止・生成数上限・context 上限に当たらない場合、2行を commit します。それ以外は現在 token の1行だけを commit します（`engine/src/qwen35/q36_engine.cu:4802-4811,4821-4858`）。
- 2行で進んだ slot は `BT` を2回出力し得ます。要求終了時は `BDONE` を stdout に出し、proposal を出した slot について受理数を stderr に出します（`engine/src/qwen35/q36_engine.cu:4834-4849`）。
- 有効時は batch session ごとの状態を使い、初期化時に各 session の K/V・GDN state 等を確保します。VRAM 不足時は初期化が失敗し、stderr に slot 数・context に対する不足を示して終了コード 1 になります（`engine/src/qwen35/q36_engine.cu:1962-1967,2145-2159`）。

## 適用条件と副作用

- 効果があるのは `--serve` の batch decode です。parser は `E.bmtp` をセットしますが、serve に入らない benchmark は別の処理を実行し、通常の `--tokens` 生成も `E.spec_step` を使うため、このフラグは batch window を選択しません（`engine/src/qwen35/q36_engine.cu:5559-5563,5572-5593,5614-5627`）。
- `--batch N` は複数 session とそれぞれの GPU state を確保するため、必要 VRAM が増えます。engine は session 数を verifier の上限 `kVerify` 以下に丸めます（`engine/src/qwen35/q36_engine.cu:1962-1967,2151-2159`）。
- `--mtp N` が正でもモデルに MTP block がなければ `E.mtp_d` は 0 になり、本オプションは有効になりません（`engine/src/qwen35/q36_engine.cu:5555-5560`）。

## 出力とエラー

- 条件不足は上記の warning を stderr に出して無視します。option 自体による parser error や終了コード変更はありません（`engine/src/qwen35/q36_engine.cu:5559-5562`）。
- 有効時の生成 token と `BDONE` は stdout、各 slot の MTP 提案受理数は stderr に出ます（`engine/src/qwen35/q36_engine.cu:4834-4849`）。複数 session の VRAM 不足は stderr に診断を出し `exit(1)` します（`engine/src/qwen35/q36_engine.cu:2151-2159`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5348-5384` — Qwen3.6 parser、値なしの flag、batch / MTP 関連値。
- `engine/src/qwen35/q36_engine.cu:5456-5461,5555-5562` — `--mtp` の範囲、モデルの MTP block を踏まえた有効条件、警告、serve への分岐。
- `engine/src/qwen35/q36_engine.cu:4759-4811,4821-4858,4900-4909` — 候補 slot の選択、MTP proposal を含む window、受理判定と出力。
- `engine/src/qwen35/q36_engine.cu:1962-1967,2151-2159` — session 数上限と VRAM 不足経路。
- `engine/src/program/generate.cpp:3808-3818` — `strata` が Qwen3.6 model を専用 parser に振り分ける経路。
