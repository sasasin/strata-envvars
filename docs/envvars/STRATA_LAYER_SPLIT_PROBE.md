# `STRATA_LAYER_SPLIT_PROBE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata generate` の CUDA レイヤー分割起動時に行う L2 startability probe の実行を切り替える診断用スイッチです。probe は、決定済みの分割で各 GPU が 512-token prompt chunk をキャッシュから借りられるか、借りられない場合に自身の buffer と 512 MiB の余裕を確保できるかを、現時点の空きメモリで確認して stderr に報告します。変数は分割位置の決定には使われず、probe の不成立も分割や起動を止めません（`engine/src/program/generate.cpp:6959-6961`, `7510-7515`, `10070-10120`）。

## 値と判定

関数内 `static const bool` の初期化 lambda で `std::getenv` を呼び、未設定なら有効、設定されていれば値の先頭文字が `'0'` でない場合に有効です。文字列全体の parse や数値検証、大文字小文字の変換はしません（`engine/src/program/generate.cpp:10074-10079`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA `strata generate` のこの実装 | 有効 | 空文字、`1`、`true`、`false`、`off`、` 0`、`0anything` 以外の文字列 | `0`、`0anything`、`00`、`0.1` など先頭が `0` の文字列 |

空文字は設定済みですが先頭が終端文字なので有効です。空白は trim されず、先頭に空白がある ` 0` も有効です。`0anything` は数値としての妥当性を問わず無効になります。先頭文字だけの判定なので、残りの文字や大文字小文字は結果に影響しません。

## 有効になる条件

- probe の実行には `--serve --layer-split auto` が必要です。`--layer-split` の解釈は `--serve` を要求し、1 枚の GPU しか分割先がない `auto` は分割なしに切り替わります（`engine/src/program/generate.cpp:4803-4809`, `4836-4840`）。
- 実行時点で `multi_gpu`、`split_auto`、`split_probe` が真で、選択済みの `split_at` が空でない場合に限って probe 本体へ進みます（`engine/src/program/generate.cpp:4856`, `10079`）。手動の `--layer-split K[,K2..]` では実行されません。
- この箇所は `cudaMemGetInfo` と CUDA device を使う CUDA 実装です。対象コードに OS 別や build macro 別の判定はありません（`engine/src/program/generate.cpp:10091-10105`）。
- probe 内の借用可否判定は `STRATA_PREFILL_LEND_PCT` と `g_lend_keep` にも依存します。`STRATA_PREFILL_LEND_PCT` は設定時に `atoi` で整数化され、未設定時は `g_lend_keep != 128` なら 100、そうでなければ pinned share が 0.9 以上なら 90、未満なら 85 が使われます（`engine/src/program/generate.cpp:10081-10085`）。

## 実行時の詳細

値は probe 条件の `if` より前にある関数内 static initializer で一度だけ読みます。したがって、実行中に環境値を変えても初期化後の値は変わりません。また、コード上は `split_probe` の初期化自体は probe 条件の有無にかかわらず、その行まで実行が到達したときに行われます（`engine/src/program/generate.cpp:10075-10079`）。

有効時は CUDA0 と後続 stage の各 GPU について、512-token 分の `bytes_needed`、キャッシュ slot 数・平均 slot bytes から見積もった必要 slot 数を計算します。必要 slot を `g_lend_keep` 以上残し、かつ `STRATA_PREFILL_LEND_PCT` の割合内で借りられるなら、その stage は合格として続行します。借りられない場合は `cudaMemGetInfo` の空き bytes と必要 bytes + 512 MiB を比較します（`engine/src/program/generate.cpp:10087-10109`）。

全 stage が probe 条件を満たす場合は成功行を stderr に出し、満たさない stage があれば最初に見つかった GPU の診断と対処候補を stderr に出します。probe 不成立は診断のみで、ここでは return、分割変更、chunk 変更を行いません（`engine/src/program/generate.cpp:10110-10120`）。後段の prompt path 初期化には別の実チェックがあり、buffer が入らない場合は chunk を縮めて再試行し、最終的に開始できなければエラーを出して終了します。この後段チェックは本変数では無効になりません（`engine/src/program/generate.cpp:13053-13140`）。

## ログと測定値

probe 有効時に全 stage が合格すると、stderr に次を出します。

```text
strata generate: layer split auto: L2 probe: the split is startable on the live free figures
```

不合格時は `strata generate: layer split auto: L2 probe: CUDA%d cannot start the prompt path: ...` と、続けて `strata generate: to make room: ...` を出します。環境変数を無効にした場合はこの probe 由来の2種類の行は出ません。実際の prompt path 初期化・縮小再試行・失敗時のログは別処理です（`engine/src/program/generate.cpp:10110-10120`, `13101-13140`）。性能測定値はこの変数について記載されたものを確認できませんでした。

## 根拠

- 変数の唯一の実行時読み取り、値判定、probe の条件・出力: `engine/src/program/generate.cpp:10070-10120`。
- `--serve` と自動分割の前提、multi-GPU 判定: `engine/src/program/generate.cpp:4803-4856`。
- 自動分割の決定が probe より前であること: `engine/src/program/generate.cpp:6959-6961`, `7510-7515`。
- probe 後も実行される prompt path の実チェックと失敗経路: `engine/src/program/generate.cpp:13053-13140`。

`docs/DETAILS.md` と関連する分割資料に、この環境変数の追加動作説明は見つかりませんでした。候補一覧 `docs/envvars/000_envvers.md` には名前がありますが、実装上も Strata が `std::getenv` で値を読む箇所を確認しました。
