# `DS4_WINDOWS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。対象は Strata 同梱 DS4 (`src/dsv41`) の実装。

## 役割

DS4 の prompt 処理で、単一 GPU・`--tp 1`・`--threads off` のときにレイヤー単位で prompt を進める chunked path を自動選択するかを制御します。`DS4_WINDOWS` が設定されていると、この自動選択を抑え、通常の 16-token window path を選びます。ここでいう windows は prompt 処理の単位で、decode のスレッド並列設定 `par` 自体は変更しません。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | chunked path の自動選択を許可 |
| 設定あり | chunked path の自動選択を抑制 |

値は文字列として読み取らず、`std::getenv("DS4_WINDOWS") == nullptr` かだけを判定します。そのため `1`、`0`、`false`、空文字を含め、何らかの値が設定されていれば同じ扱いです。数値変換や大文字小文字の比較はありません。根拠: `src/dsv41/ds4_model.cu:1925-1931`。

## 有効になる条件

次の式で `prompt_par` を決めています:

```cpp
par || o.tp > 1 ||
((o.prefill_chunk > 0 || (o.prefill_chunk < 0 && kChunkedPromptDefault)) &&
 std::getenv("DS4_WINDOWS") == nullptr)
```

`kChunkedPromptDefault` は `true` です (`src/dsv41/ds4_model.cu:809-815`)。したがって、`par` が false で `tp` が 1 の場合に限り、`DS4_WINDOWS` の有無がこの式に影響します。

- `--threads on` または `--tp` が 1 より大きいと、先行条件で `prompt_par` が true になり、この変数は選択を変えません。
- `--tp 1 --threads off` で `--prefill-chunk` を省略した場合、未設定なら既定で chunked path、設定ありなら window path です。
- 同じ実行条件で `--prefill-chunk N`（`N > 0`）を指定しても、`DS4_WINDOWS` が設定されていると `prompt_par` が false になり、chunk は使われません。変数未設定なら指定値が使われます。
- `--prefill-chunk 0` は chunked path を要求しないため、`DS4_WINDOWS` の有無にかかわらず `--tp 1 --threads off` では window path です。

## 実行時の詳細

変数は `Model::Impl::load()` の GPU/グループ設定時に読み取られ、各 prompt 処理で読み直すものではありません (`src/dsv41/ds4_model.cu:1860-1863,1919-1932`)。chunk サイズは `prompt_par` が true の場合に `--prefill-chunk` の値または `prefill_chunk_default(...)` の結果から決まり、false の場合は 0 になります。その後 `DS4_CHUNK` が設定されていても `prompt_par` が false なら chunk は 0 のままです (`src/dsv41/ds4_model.cu:1990-1999`)。

chunk 用 buffer の確保に失敗し、chunk を 0 まで縮めた場合も、実装は `prompt_par` を false にして 16-token window path に切り替えます。このとき stderr に `ds4: the prompt path's buffers did not fit ... prompts run in windows of ...` を出します (`src/dsv41/ds4_model.cu:2623-2637`)。初期化時に chunk が 0 だった場合は、別の `ds4: prompts run in windows of ...` メッセージを出します (`src/dsv41/ds4_model.cu:2002-2009`)。

## 根拠

- `src/dsv41/ds4_model.cu:809-815` — `prompt_par` と既定 chunked path の定義。
- `src/dsv41/ds4_model.cu:1919-1932` — `par`、`tp`、`--prefill-chunk`、`DS4_WINDOWS` の判定。
- `src/dsv41/ds4_model.cu:1990-2009` — chunk 値の決定、`DS4_CHUNK` の適用、window path のログ。
- `src/dsv41/ds4_model.cu:2623-2637` — chunk buffer 確保失敗時の縮小と window path への fallback。
- `src/dsv41/ds4_main.cpp:1235-1237` — `--tp`、`--prefill-chunk`、`--threads` の CLI 値の設定。
- `src/dsv41/ds4_experts_rule.hpp:41-51` — 自動 chunk サイズを決めるルール。`DS4_WINDOWS` 自体の判定根拠ではない。

`docs/DETAILS.md` と関連する設計資料には `DS4_WINDOWS` の直接説明を確認できませんでした。この文書の挙動説明は上記 HEAD の実装に基づきます。
