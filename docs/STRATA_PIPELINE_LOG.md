# `STRATA_PIPELINE_LOG`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows 2` の speculative decode ループで、window chain の作成と verdict（検証結果）を stderr に記録する診断用スイッチです。CUDA と SYCL の生成コードにそれぞれログ分岐があります。トークン生成や pipeline の選択自体はこの変数では変わりません。

## 値と判定

`STRATA_PIPELINE_LOG` の値は parse されず、`getenv()` の結果が null かどうかだけを見ます。空文字を含め、何らかの値が設定されていればログ要求になります。ただし `pipe_dbg_env()` が先に `STRATA_PIPELINE_DEBUG` のゲートを適用します。

| 状態 | 結果 |
|---|---|
| `STRATA_PIPELINE_DEBUG` 未設定、空文字、または先頭文字が `0` | `pipe_dbg_env()` は常に null を返すため、`STRATA_PIPELINE_LOG` は無効 |
| `STRATA_PIPELINE_DEBUG` が設定され、空でなく、先頭文字が `0` 以外。`STRATA_PIPELINE_LOG` は未設定 | ログ無効 |
| 同じデバッグゲート条件を満たし、`STRATA_PIPELINE_LOG` が設定済み | ログ有効。値が空、`0`、`false` などでも有効 |

`STRATA_PIPELINE_DEBUG` の大文字小文字や数値としての妥当性は検査されず、先頭文字だけで判定します。たとえば `false` はデバッグゲートを有効にし、`0anything` は無効にします。`pipe_dbg_env()` 内のゲート値は関数ローカル `static` に保存され、`pl_log` も `static const bool` です。各値は最初に評価された後、プロセス内で環境を変更しても再評価されません。

根拠: `src/program/generate.cpp:251-257`、`sycl/src/program/generate.cpp:293-298`、`src/program/generate.cpp:11205`、`sycl/src/program/generate.cpp:10457`。

## 有効になる条件

- 生成サーバーで layer-split の pipeline 経路を実行し、2-window decode が実際に走ることが必要です。CUDA 側では `pl_want` が `pipe && pl_pw >= 2 && pl_snap_ok`、SYCL 側では `pipe && pl_pw >= 2 && pl_snap2[0] != nullptr` のときに pipeline ループへ入ります。
- `--pipeline-windows` の値が 0/1、適用条件不成立、snapshot 準備失敗などで2-window経路に入らない場合、このログスイッチは参照されず、出力しません。
- `STRATA_PIPELINE_DEBUG` は tuning/test 用 `STRATA_PIPELINE_*` 変数を読むためのゲートです。未設定などの場合は `STRATA_PIPELINE_LOG` を設定しても無効です。

この変数の直接参照は通常の CUDA 生成コードと SYCL 生成コードにあります。HIP は `src/program/generate.cpp` の共通生成経路を使います。別の GPU driver や外部ライブラリの環境変数動作はここでは扱いません。

根拠: `src/program/generate.cpp:6976-6979,10424-10434,11205`、`sycl/src/program/generate.cpp:10424-10457`。

## 実行時の詳細

ログ要求は2-window pipeline ループに入る直前に `pl_log` として一度評価されます。ログを有効にしたとき、chain を作った箇所で、chain 種別、position、window 長、後続 B window の長さ、推定確率 `p_on`、出力数を含む `strata pipeline: chain ...` を stderr に出します。各 verdict では position、検証 window 長、受理数 `a`、後続 window の状態（`launched` / `ready` / `none`）と on-path 判定を `strata pipeline: verdict ...` として出します。CUDA 版は verdict の `out` に出力 token ID も続けて記録します。SYCL 版の verdict 行は token ID を列挙しません。

このログは生成の進行中に stderr へ出る診断情報です。`STRATA_PIPELINE_LOG` 自体は標準出力の応答、終了条件、pipeline の動作を変更しません。

根拠: `src/program/generate.cpp:11581-11584,11700-11707`、`sycl/src/program/generate.cpp:10896-10899,11006-11008`。

## 文書との照合

`docs/MULTI_GPU.md` は pipeline の tuning/test 変数に `LOG` を含め、これらが `STRATA_PIPELINE_DEBUG=1` のときだけ読まれると説明しています。実装のゲートは厳密な文字列 `1` 比較ではなく、「空でない値で、先頭文字が `0` ではない」という判定です。そのため文書の `=1` は代表的な有効値として読む必要があります。ログの具体的な文言と出力項目は実装の `fprintf(stderr, ...)` に従いました。

根拠: `docs/MULTI_GPU.md:311-314`、`src/program/generate.cpp:254-256`。

## 根拠

- `src/program/generate.cpp:251-257`: 共通 debug gate helper。
- `src/program/generate.cpp:10424-10434,11205`: CUDA pipeline 適用条件とログ判定。
- `src/program/generate.cpp:11581-11584,11700-11707`: CUDA chain/verdict ログ。
- `sycl/src/program/generate.cpp:293-298`: SYCL 側 debug gate helper。
- `sycl/src/program/generate.cpp:10424-10457,10896-10899,11006-11008`: SYCL pipeline 適用条件、ログ判定、出力。
