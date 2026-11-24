# `STRATA_INK_PREFILL_CAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`strata-inkling --serve` の連続バッチ処理で、別 slot が decode 中に prompt prefill に回す token 予算を抑える値です。正の値を設定すると、decode token を先にバッチへ入れた後、prefill 用の残り予算に上限を設けます。decode 用 token 自体や prompt/decode の結果を変更する分岐ではなく、各 step で同時に処理する prefill token 数と step の配分を変えます。実装は `run_serve_loop` にあります（`engine/src/inkling2/ink_serve.h:494-507,1003-1058`）。

この値は `--serve` 経路で `run_serve_loop` が実行されるときだけ読み取られます。通常の直接 CLI 生成、`--bench`、`--selfcheck` などはこのループに入らないため、この変数による制御はありません（`engine/src/inkling2/ink_main.cpp:1039-1071,1078-1095`）。読み取り箇所に OS・backend・GPU 世代・build macro による条件分岐はありません。設定一覧は NVIDIA / AMD 向けと分類し、terminal の設定登録データも `cuda-hip` の読み取り記録を載せていますが、いずれも追加の実行時読み取り箇所ではありません。ここで確認できるソース上の適用条件は serve loop の実行です（`docs/SETTINGS.md:122`; `terminal/data/settings-register.json:17084-17094`）。

## 値と判定

serve loop の開始時に `prefill_cap` を 0 で初期化し、環境変数が未設定でなく、かつ空文字でなければ `std::atoi` で変換した値と 0 の大きい方を使います。空文字は未設定と同じ既定値 0 です。`atoi` は整数として読める先頭部分を変換し、文字列全体の妥当性を検査しません。したがって `64tail` は 64、`true` や `0anything` は 0 になり、符号や先頭空白を含む数値も `atoi` の規則で変換されます。負数は `std::max(0, ...)` で 0 にされます。0 は上限なしとして扱われます。明示的なエラー・警告・fallback ログはありません（`engine/src/inkling2/ink_serve.h:499-506`）。

| 条件 | unset | 有効になる値 | 上限を使わない値 |
| --- | --- | --- | --- |
| `run_serve_loop` 内 | 0（上限なし） | `64`, `+64`, ` 64`, `64tail` など、`atoi` 結果が正の値 | 空文字、`0`, `0anything`, `true`, `-1`, `-64` など、未設定または変換後が 0 以下 |

`atoi` の変換可能範囲を超える数値文字列に対する結果はこの実装で検査・処理していないため、値として保証できません。CLI 引数や別の環境変数でこの値を上書きする処理はありません。

## 有効になる条件

- `strata-inkling` が `--serve` を受け取り、モデルと backend の初期化後に serve loop を実行すること（`engine/src/inkling2/ink_main.cpp:858-860,1078-1095`）。
- 環境変数の変換結果が正であること。
- 同じ step に、decode を進めている slot（`logit_slots` が空でない）と、prefill 中の slot があること。prefill 中の slot がなければ制限対象がありません。decode 中の slot がなければ、この上限を適用する分岐には入りません（`engine/src/inkling2/ink_serve.h:1013-1032`）。
- バックエンドが当該バッチの forward を実行できること。値は backend の種類を選択せず、forward 失敗時のエラー処理も置き換えません（`engine/src/inkling2/ink_serve.h:1063-1100`）。

## 実行時の詳細

環境変数は `run_serve_loop` 呼び出しごとに一度読み、ローカル変数 `prefill_cap` に保存します。step ごとや request ごとに再読込せず、実行中にプロセス環境を変更しても現在の loop には反映されません（`engine/src/inkling2/ink_serve.h:494-506`）。

各 step の token budget は `max(chunk_sz, n_active)` で始まり、まず各 decode 中 slot の token をバッチへ追加して、その数だけ budget を減らします。decode が一つ以上ある場合、正の `prefill_cap` が残り budget の上限となります。その後、残り budget を prefill 中 slot 数で割り、各 slot に割り当てる数を `max(1, budget / prefill slot 数)` とします。各 request の残 prompt 数、prompt 終端 checkpoint の保存位置、shared-prefix の位置に応じて実際に追加する数をさらに制限します（`engine/src/inkling2/ink_serve.h:1003-1058`）。

そのため、この値は「decode がある step で prefill に割り当てる予算」を制御しますが、常に全 prefill token 数の厳密な総上限になるわけではありません。上限後の budget が prefill 中 slot 数より小さい場合でも、整数除算の結果を最低 1 にするため、複数 slot が各 1 token を受け取り、合計が設定値を超えることがあります。また decode がない step は上限分岐を通らず、通常の chunk budget で prefill します。値は `chunk_sz` や CLI の `--chunk` を変更せず、それらから計算した step budget に作用します（`engine/src/inkling2/ink_serve.h:497-498,1009-1058`; CLI の chunk 設定は `engine/src/inkling2/ink_main.cpp:879-881`）。

## ログと測定値

この変数の値、parse 結果、上限適用を示す専用ログはありません。serve loop の `INFO` 行にも値は含まれません（`engine/src/inkling2/ink_serve.h:562-568`）。この変数自体に対応する無効値警告や終了経路もありません。後続の backend forward が失敗した場合は、既存処理により KV 容量不足なら stderr に `[ink-serve] slot %d ended at %d tokens: %s` を出して該当 request を `length` で終了し、それ以外は `ERR fatal GPU error: %s` を protocol 出力して loop から 1 を返します。これはこの環境変数専用の失敗ではありません（`engine/src/inkling2/ink_serve.h:1083-1100`）。

ソースコメントには RTX 5090 での cap 別 decode 速度と prompt first-token 時間の数値がありますが、モデル・backend・設定など測定条件が十分でないため、一般的な測定値としては記載しません（`engine/src/inkling2/ink_serve.h:499-502`）。

## 根拠

- `engine/src/inkling2/ink_serve.h:494-507` — serve loop と環境変数の読み取り・既定値・変換。
- `engine/src/inkling2/ink_serve.h:1003-1058` — decode 優先の token budget、cap 適用、prefill slot への配分。
- `engine/src/inkling2/ink_serve.h:562-568,1083-1100` — serve の INFO 行と forward 失敗時の観測可能な処理。
- `engine/src/inkling2/ink_main.cpp:858-860,1078-1095` — `--serve` の設定と serve loop 呼び出し。
- `engine/src/inkling2/ink_main.cpp:879-881` — CLI `--chunk` の設定。
- `docs/SETTINGS.md:122`、`terminal/data/settings-register.json:17084-17094` — 設定一覧・登録データ上の分類と読み取り記録（実装上の読み取り箇所は `ink_serve.h:506`）。
