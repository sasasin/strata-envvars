# `STRATA_DF2_END_UPDATE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`strata serve` のリクエストが EOS または生成上限で終わり、次の DFlash2 draft を作らない場合に、その窓で確定した verifier の tap 行を DFlash2 の context に反映するかを制御する。既定では反映する。これにより、続く会話ターンで再開したときに DFlash2 の K/V ring と記録に確定行を残す。`0` でこの終端更新を抑止する。対象は DFlash2 を実際に使うサーバー経路であり、通常の `strata generate` 用ループにはこの環境変数の参照がない。(`engine/src/program/generate.cpp:23131-23139`, `engine/src/program/generate.cpp:24948-24955`)

## 値と判定

値を数値や真偽値として parse せず、`std::getenv` の結果が未設定なら有効、設定済みなら先頭文字が `'0'` 以外のとき有効とする。文字列全体、空白、大文字小文字は検査しない。空文字列は先頭が終端文字 `\0` なので有効。先頭が `0` なら後続の内容にかかわらず無効で、`0` と `0anything` は同じ判定になる。`1`、`true`、`false`、` 0` は有効である。(`engine/src/program/generate.cpp:23135`)

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_HAVE_DFLASH2` が定義されたビルド | 有効 | 空文字、`1`、`true`、`false`、` 0` | `0`、`0anything` |
| `STRATA_HAVE_DFLASH2` が未定義のビルド | このコードはコンパイル対象外 | 該当なし | 該当なし |

## 有効になる条件

- 終端更新のコードは `STRATA_HAVE_DFLASH2` の条件付きコンパイル内にある。CUDA/HIP 共通ビルド設定はこの macro を定義する（`engine/cmake/strata_gpu_engine.cmake:9-14`）。Metal の host target も定義している一方（`engine/metal/CMakeLists.txt:154-157`）、同ファイルには DFlash2 を CUDA/HIP のみとするコメントもあり、Metal でのこの処理の実際のビルド可否はソース調査だけでは確認していない。SYCL は別の移行済み `generate.cpp` をビルドし（`engine/sycl/CMakeLists.txt:3-7,375-377`）、リポジトリ全体検索でも対象名の参照はなかった。
- サーバーループで DFlash2 が利用可能 (`use_df2`) で、当該リクエストも DFlash2 を選択 (`req_df2`) している必要がある。`--draft auto` の場合、リクエストの `draft` 指定または `--draft-rule` による選択が `dflash2` / `df2` なら対象になり、`mtp` なら対象外（`engine/src/program/generate.cpp:18924`, `engine/src/program/generate.cpp:18944-19005`）。DFlash2 の起動・tap 準備に失敗して `use_df2` が解除された場合も対象外（同 `13584-13613`）。
- merged window ではないこと、およびその窓が EOS (`eos`) または `cap_now()` に達していることが必要。DFlash2 が無効、リクエストが MTP を選択、merged window、または上限未到達で EOS でもない場合は、この終端更新を行わない（`engine/src/program/generate.cpp:23136`）。
- `strata generate` の通常生成ループや DFlash2 を使わない実行では、この分岐は働かない。CLI の `--draft` はこの条件を上書きしない。サーバーリクエストの `draft` は `--draft auto` のときに選択へ使われる。

## 実行時の詳細

値は `generate.cpp` のサーバー要求処理中にある関数内 `static` の初期化で読み取られる。最初にこの行へ到達したときに一度だけ評価・保存され、その後にプロセス環境を変えても反映されない。式は未設定判定のあと、設定済みの場合にもう一度 `getenv` を呼び、先頭文字だけを調べる（`engine/src/program/generate.cpp:23135`）。

条件を満たすと、現在の verifier window の `a + 1` 行分の tap を `df2_win_taps` から取得し、位置 `p` から `df2.context` に渡す。複数 GPU の layer split では `df2_win_taps` が各 stage の tap を drafter 側へ gather する（`engine/src/program/generate.cpp:13616-13620`, `engine/src/program/generate.cpp:23136-23138`）。DFlash2 側の `context` は入力 tap から context 処理を行い、成功時に保持 context/ring の上端を進める（`engine/src/core/dflash2.cpp:1044-1048`, `engine/src/core/dflash2.cpp:1120-1142`）。

tap の取得が失敗するか `df2.context` が失敗すると、適応スレッドがあれば join した後、標準出力へ `ERR ` と `err` の内容を出し、そのエンジン処理は `return 1` で終了する。環境変数自体について専用の有効化・無効化ログはない（`engine/src/program/generate.cpp:23137-23138`）。

## ログと測定値

この変数専用のログや、この終端更新の性能・正確性に関する測定値は確認できない。失敗時の標準出力は `ERR %s\n` 形式で、実際の文字列は tap 取得または DFlash2 context が設定した `err` による（`engine/src/program/generate.cpp:23137-23138`）。

## 根拠

- `engine/src/program/generate.cpp:23131-23139` — 終端更新の macro guard、読み取り、適用条件、tap/context 呼び出し、失敗経路。
- `engine/src/program/generate.cpp:18924-19005` — サーバー要求ごとの drafter 選択と `req_df2`。
- `engine/src/program/generate.cpp:13584-13620` — DFlash2 のサーバー利用準備、fallback、layer split の tap gather。
- `engine/src/program/generate.cpp:24948-24955` — 通常の生成ループにおける DFlash2 draft 処理。環境変数参照はない。
- `engine/cmake/strata_gpu_engine.cmake:9-14`, `engine/metal/CMakeLists.txt:154-157`, `engine/sycl/CMakeLists.txt:3-7,375-377` — build macro と SYCL の別ソース構成。
- `engine/src/core/dflash2.cpp:1044-1142` — DFlash2 context 処理と成功時の context/ring 位置更新。
