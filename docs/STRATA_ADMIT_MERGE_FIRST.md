# `STRATA_ADMIT_MERGE_FIRST`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata serve --batch` の新規スロットへの admission（`BGEN` / `BGENI`）で、プロンプト末尾の複数 token と最初の生成 token を、条件がそろう場合に同じ verify window で処理します。通常はプロンプト末尾の token までを prompt window で読み、その後に最後の prompt token から最初の生成 token を出す window を実行します。この変数が有効で適用条件を満たすと、末尾の prompt token を含む最大 `max_t` 個の token を最初の window にまとめます。

## 値と判定

| 環境変数 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 有効 |
| 先頭文字が `0` | 無効（例: `0`, `0abc`） |
| それ以外 | 有効（例: `1`, `true`, `false`, `2`） |

値全体の parse、数値変換、大文字小文字の判定はありません。判定関数の関数内 `static const bool` に結果を保存するため、プロセス中の最初の呼び出しで読み取られ、その後の環境変更は再評価されません。`STRATA_LOGPOS` は別の環境変数で、値ではなく設定有無がこの最適化の gate になります。

根拠: `src/program/generate.cpp:179-190,13368-13374`。

## 有効になる条件

値判定が有効でも、次の条件をすべて満たす windowed prompt の最終 segment に限って適用されます。

- `BGEN` / `BGENI` でバッチ slot への admission 中である。
- その admission の `max_new` が `1` で、`--batch-mtp` と `--pipeline-windows` の経路ではない。
- 処理対象が prompt の最後の cut (`to == n - 1`) で、turn/root/message checkpoint や pin の境界ではない。
- 画像入力、KV growth、peer/remote cache・remote option、filesystem swap がない。
- `STRATA_LOGPOS` が未設定である（空文字でも設定済みとして無効化）。
- host residency table があり、pending swap がなく、table に負値の slot がない。
- 全 stage の verifier で `ar_live()` が true である。これは expert が全て VRAM にあり、zero-doorbell graph を使える状態かを host table と照合する gate。
- 全 stage の `max_t()` の最小値が少なくとも 2 である。

条件に合わない場合は `merge_from()` が `-1` を返し、従来どおり最後の prompt token を単独で処理する最初の window に進みます。したがって環境変数を有効にするだけでは、全 prompt や単独 generate の経路でこの処理は有効になりません。

根拠: `src/program/generate.cpp:13362-13404`; `include/strata/core/verify.hpp:179-181,461`。

## 実行時の詳細

`BGEN` / `BGENI` を受け取ると serve loop は `admit_slot` を設定して、通常の `GEN 1` / `GENI 1` 処理へ変換します。prompt を区切る最終 segment が windowed (`windows_ok`) なら、refill 後に `merge_from()` が gate を評価します。成功時は `merge_at = max(a0, n - mt)` となり、prompt のそれ以前の範囲を通常どおり読み、末尾 `[merge_at, n)` は prompt-read loop から残します。

prompt-read loop は通常、verify window で各 prompt token を commit し、head sampling を無効にして予測を捨てます。続く最初の decode window は `merge_T = n - merge_at` を行数に設定し、prompt の token を入力に使います。実装コメントでは、最後の prompt token と最初の生成 token を同じ window に置き、各 row の計算結果と Philox draw を通常の window と一致させる意図が記されています。ここで `max_new == 1` が gate に含まれるため、この admission で同じ window に複数の生成 token をまとめる設定ではありません。

通常の `STRATA_TRACE` が有効なら、成功時に stderr へ `strata trace: the first window takes the last %lld prompt tokens`（`%lld` は実際の token 数）が出ます。prompt window read のエラー処理や `PP` / `REUSED` 出力は通常経路を通ります。

根拠: `src/program/generate.cpp:11305-11347,12517-12528,12531-12566,13362-13424,13479-13490,14204-14243`。

## 文書との照合

`docs/BATCHING.md:110-120` は opt-in switch として、admission が最後の prompt token 群と最初の token を一つの window で読むこと、および全 expert が resident の場合に限ることを記載しています。実装ではさらに上記の admission、最大生成数、checkpoint、backend/resource 状態などの gate が確認できます。測定値や性能向上はこの文書では主張しません。

## 根拠

- `src/program/generate.cpp:179-190`: 値の判定と一度だけの読み取り。
- `src/program/generate.cpp:11305-11347`: `BGEN` / `BGENI` の admission 識別。
- `src/program/generate.cpp:13362-13404`: merge の条件、window 上限、prompt 読み取り位置。
- `src/program/generate.cpp:12517-12566,13479-13490,14204-14243`: prompt windows と最初の merged window の処理。
- `include/strata/core/verify.hpp:179-181,461`: residency gate。
- `docs/BATCHING.md:110-120`: 関連する機能説明。
