# `STRATA_KVA_CAPTURE_FP32`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_KVA_CAPTURE` で KVA の入力 capture を行うとき、各 late layer の入力行を fp32（4-byte float）で書くか、既定の bf16（2-byte）で書くかを選ぶ。fp32 は parity run 用で、値を変えても prompt の計算経路は変わらない。capture 中は KVA 近似を行わず、通常どおり全層を計算した入力を保存する（`engine/include/strata/prefill/kva.hpp:79-80, 143-167`; `engine/src/prefill/prefill.cpp:4997-5007, 5067-5071`）。

この名前の実際の読み取りは `kva_config_from_env()` 内の `kva_env_flag("STRATA_KVA_CAPTURE_FP32", false)` の一箇所。メンバー初期値も false で、`STRATA_KVA_CAPTURE` が空でない場合に限って helper が呼ばれる（`engine/include/strata/prefill/kva.hpp:79-80, 143-167`）。

## 値と判定

helper は `std::getenv` の結果が null または空文字なら既定値を返し、それ以外は先頭文字が `'0'` でない場合に true とする。文字列全体の parse はなく、数値妥当性・空白・大文字小文字も検査しない（`engine/include/strata/prefill/kva.hpp:143-147`）。

| 条件 | unset | 設定時に有効になる値（fp32） | 設定時に無効になる値（bf16） |
|---|---|---|---|
| `STRATA_KVA_CAPTURE` が空でない | false | 先頭が `0` 以外（例: `1`, `true`, `2`, ` 0`） | 先頭が `0`（例: `0`, `0anything`）。空文字は unset と同じ false |

例えば `false` や ` 0` は先頭が `0` ではないため fp32、`00` や `0xyz` は bf16 になる。capture 出力先が未設定または空文字なら、この変数は読み取られず、値が設定されていても出力形式に影響しない（`engine/include/strata/prefill/kva.hpp:143-167`）。

## 有効になる条件

- `STRATA_KVA_CAPTURE` に空でないディレクトリ文字列を設定する。これがない場合、対象変数を読む helper 呼び出しに到達しない（`engine/include/strata/prefill/kva.hpp:163-167`）。
- capture tap は全 trunk の prefill（`LB == 0` かつ `LE < 0` または `LE == g.n_layers`）で、`STRATA_KVA_SPLIT` を反映した split 以上の layer に限られる。既定 split は 36 で、実行時には 1 から layer 数の範囲に丸められる（`engine/include/strata/prefill/kva.hpp:54-57, 85, 157`; `engine/src/prefill/prefill.cpp:4245-4246, 4997-5007`）。
- `STRATA_KVA=1` は capture の必要条件ではない。capture が有効なら `decline()` は capture mode を理由に近似を退け、`kva_run` は false になる一方、`kva_cap_layer` による入力保存は別に実行される（`engine/include/strata/prefill/kva.hpp:108-115`; `engine/src/prefill/prefill.cpp:4233-4244, 4997-5007`）。
- `STRATA_KVA_CAPTURE_FP32` と CLI 引数の優先順位・上書き分岐は実装にない。`STRATA_KVA_CAPTURE` が capture の有無を決め、この変数はファイル要素幅だけを選ぶ（`engine/include/strata/prefill/kva.hpp:163-167`; `engine/src/prefill/prefill.cpp:4150-4163`）。
- `kKvaBackend` は Metal build で false になるが、この対象変数を読む条件および capture tap 条件は同値を参照していない。したがって、このコード上で確認できる capture の条件は上記の `STRATA_KVA_CAPTURE` と全 trunk / split 条件である（`engine/include/strata/prefill/kva.hpp:43-49, 143-167`; `engine/src/prefill/prefill.cpp:4997-5007`）。

## 実行時の詳細

本番経路は `kva_config()` の関数内 `static const KvaConfig` に設定を保存する。設定はプロセス内で初回アクセス時に一度読み取られ、後続の prefill や実行中の環境変更では再評価されない。generate の engine 初期化時にも `kva_config()` が参照される（`engine/include/strata/prefill/kva.hpp:149-167, 191-195`; `engine/src/program/generate.cpp:8093-8104`; `engine/src/prefill/prefill.cpp:4227-4235`）。

capture が有効な layer では、層に入る residual `R` を GPU から host へコピーし、`STRATA_KVA_CAPTURE_FP32` が true なら fp32 配列をそのまま書く。false なら各 fp32 値を最近接偶数丸めで bf16 に変換して書く。出力名は `L<layer>.bin`、1 layer につき1ファイルで、prompt の位置順に chunk 行を追記する。新しい cold prompt の capture 開始時にはファイルを閉じ、position を先頭に戻す。各 layer のファイルは初回書込み時に `wb` で開くため、既存ファイルは切り詰められる（`engine/src/prefill/prefill.cpp:4098-4109, 4122-4128, 4130-4164, 4247-4252, 5067-5071`）。

Strata は出力ディレクトリを作成しない。GPU residual のコピーまたは同期に失敗すると `kva capture: the residual copy failed`、ファイルを開けないと `kva capture: cannot write <path>` を `err` に設定して prefill を失敗させる。`fwrite` と `fflush` の戻り値は検査されないため、それらの書込み失敗を Strata が検出する経路はこの実装にはない（`engine/src/prefill/prefill.cpp:4140-4164, 5067-5071, 9705-9713`; `engine/src/program/generate.cpp:24058-24060`）。

## ログと測定値

成功時の prefill は stderr に `strata prefill: KVA off (capture): split ...` と出し、capture が有効なら末尾に `, capturing the late layers' inputs` を付ける。fp32 / bf16 の選択値そのものを示す個別ログはない（`engine/src/prefill/prefill.cpp:8008-8019`）。

上記の residual コピーまたはファイル open の失敗では、prefill error が `strata generate: <err>` として stderr に出て、generate は status 1 で終了する（`engine/src/prefill/prefill.cpp:4140-4149, 5067-5071`; `engine/src/program/generate.cpp:24058-24060`）。この変数について Strata ソースに条件付き測定値はない。

## 根拠

- `engine/include/strata/prefill/kva.hpp:79-80, 137-167, 191-195` — 対象変数の既定値、helper の判定、capture 設定時だけの読み取り、process 内 cache。
- `engine/src/prefill/prefill.cpp:4227-4252, 4997-5007, 5067-5071` — 設定利用、capture 条件、近似処理との関係、write failure の伝播。
- `engine/src/prefill/prefill.cpp:4096-4164, 8008-8019` — 記録形式・ファイル処理と stderr ログ。
- `engine/src/program/generate.cpp:8093-8104, 24058-24060` — engine 初期化での設定参照と prefill failure の終了経路。
