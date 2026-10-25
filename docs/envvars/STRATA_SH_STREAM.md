# `STRATA_SH_STREAM`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

MoE の shared expert（共有 expert）計算を、routed experts の処理と並行する別 GPU stream に分岐するかを制御します。分岐した場合、layer 内で event を使って分岐元と shared expert の完了を接続し、その後 shared expert の結果を routed expert の結果と combine します。環境変数は計算方式を切り替え、shared expert 自体を省略するものではありません。

CUDA 実装と SYCL 実装の verifier が同じ値判定を持ちます。CUDA verifier は `src/core/verify.cpp`、SYCL verifier は `sycl/src/core/verify.cpp` にあります。

## 値と判定

値全体を parse せず、設定値の先頭文字だけを調べます。未設定時の値は backend によって異なります。

| 状態 | CUDA (`STRATA_USE_HIP` なし) | HIP (`STRATA_USE_HIP`) |
|---|---:|---:|
| 未設定 | 有効 | 無効 |
| 設定値の先頭文字が `0` | 無効 | 無効 |
| 空文字、または先頭文字が `0` 以外 | 有効 | 有効 |

たとえば `false`、`off`、`2` は先頭文字が `0` ではないため有効です。`0`, `0anything` は無効です。空文字は「設定済み」として扱われ、先頭文字が `\0` なので有効になります。大文字小文字、空白、数値としての妥当性は検査されません。

値は `sh_stream_on()` の `static const bool` として初回呼び出し時に評価されます。そのため初回判定後にプロセス環境を変更しても再評価されません。CUDA では初回判定前にアーキテクチャ既定値の適用はありません。HIP は後述の gfx1151 既定値適用後に判定されます。

根拠: `src/core/verify.cpp:212-222`, `sycl/src/core/verify.cpp:162-172`。

## 有効になる条件

値判定が有効でも、実際に fork されるのは verifier が profiling 中でなく、分岐用 stream と fork/join event が利用可能なときです。CUDA は `sh_cs_`, `ev_fork_`, `ev_join_` が必要です。SYCL では分岐先 queue が in-order queue と異なり、両 event が利用でき、stepped 実行でないことも条件です。これらの条件を満たさないと、shared expert は通常の verifier stream で実行されます。

HIP では未設定時は無効です。ただし `src/program/generate.cpp` と `sycl/src/program/generate.cpp` は HIP ビルドでデバイス情報を取得し、engine の switch 初回読み取り前に `apply_arch_defaults()` を呼びます。gfx1151 用の既定値表は `STRATA_SH_STREAM=1` を含み、ユーザー環境に同名変数が既に存在すれば、空文字を含めその値を上書きしません。したがって gfx1151 では通常既定で有効、明示的に `0` で始まる値なら無効です。gfx1151 以外の AMD GPU にはこの既定値は入りません。`STRATA_GFX1151_DEFAULTS` の先頭文字が `0` なら gfx1151 の既定値表自体が適用されず、未設定の `STRATA_SH_STREAM` は無効になります。

根拠: `src/program/generate.cpp:2248-2254`, `sycl/src/program/generate.cpp:2016-2022`, `src/core/arch_defaults.cpp:32-35, 56, 61-70`。

## 実行時の詳細

CUDA verifier は有効条件を満たす layer で shared expert 用 stream を選び、必要な箇所で `ev_fork_` を記録して shared stream を待たせます。shared expert の入力変換と `shared_expert_multi()` はその stream に投入され、処理後に `ev_join_` を記録します。routed expert 側の処理後、combine 前に主 stream が join event を待ちます。fork が無効なら shared expert は主 stream を使います。`STRATA_SH_FORK_LATE` は fork を layer の先頭で行うか routed work の公開後に行うかに関係する別変数で、shared stream の有効判定そのものは変えません。

SYCL verifier も別 queue に shared expert を投入し、fork/join event の barrier で依存関係を接続します。profiling 時は fork と join wait の条件から除外されます。SYCL の stepped 実行では fork しません。

実装には `STRATA_SH_STREAM` 自体の有効・無効ログや警告はありません。HIP gfx1151 でアーキテクチャ既定値が適用された場合は、設定された speed switches の件数を示す起動ログが出ますが、そのログが個別にこの変数の動作を報告するわけではありません。

根拠: `src/core/verify.cpp:1453-1464, 1546-1576, 1682-1686`; stream/event の作成は `src/core/verify.cpp:769-779`。SYCL 側の分岐条件と join は `sycl/src/core/verify.cpp:1285-1293, 1487-1493`。

## 文書との照合

`docs/AMD_HIP.md:213-217` は HIP での通常既定 OFF、gfx1151 の例外、カードにより測定結果が異なることを説明しています。`docs/STRIX_HALO.md:98` は gfx1151 での有効化と、8K decode に関する記載値（UD-IQ4_XS +1.8%、UD-Q4_K_XL +6.7%）を載せています。`src/core/verify.cpp:204-211` の注釈にも別測定の条件が記されています。これらは文書・注釈上の測定報告であり、本調査で性能を再測定した結果ではありません。コード上の機能は shared expert を別 stream/queue に分岐することで、性能効果は backend と GPU に依存します。
