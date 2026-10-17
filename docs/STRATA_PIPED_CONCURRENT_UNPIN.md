# `STRATA_PIPED_CONCURRENT_UNPIN`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 所有ソース。外部ライブラリや GPU driver の動作は含めない。

## 役割

`STRATA_PIPED_CONCURRENT=1` で使う、slot の pipelined decode と同時にプロンプトを読む経路で、読み取り thread と doorbell thread、および一部の既存 thread の CPU 配置を制御する補助スイッチです。既定では、host thread の CPU に留まりやすい thread を host の CPU から移します。`=0` はこの移動を抑え、継承した CPU affinity のままにする A/B 用設定です。

この変数は並行読み取り自体を有効にしません。親の `STRATA_PIPED_CONCURRENT` が有効で、pipelined 経路が選ばれた場合にだけ評価されます。

## 値と判定

値は `std::atoi` で整数化され、結果が 0 かどうかで判定されます。文字列全体の妥当性検査はありません。

| 値 | `conc_unpin` | 動作 |
|---|---:|---|
| 未設定 | true | CPU 配置の移動を許可（既定） |
| 空文字 | false | `atoi("") == 0` のため移動しない |
| `0`、`00`、`abc`、`  ` | false | `atoi` の結果が 0 |
| `1`、`-1`、`2`、`1abc`、` 1` | true | `atoi` の結果が非 0 |

数値変換は C の `atoi` に従い、先頭の空白と符号を扱い、数字列の後ろは検査しません。数値として範囲外の文字列に対する挙動はこの実装で別途検証・定義していません。判定値は関数内の `static const bool` に保存されるため、この経路で初めて判定した後に環境を書き換えても再評価されません。

根拠: `src/program/generate.cpp:12909-12912`。

## 有効になる条件

- `--batch > 0`、`--batch-groups > 1`、layer split の stage 数が 1 より大きく、`piped` 経路に入ること（`src/program/generate.cpp:11092-11094`）。
- `STRATA_PIPED_CONCURRENT` が設定され `atoi` の結果が非 0 であること。さらに、`STRATA_PREFILL_HELP`、`STRATA_SPLIT_MTP_BATCH`、`STRATA_FS_SLOTS`、`--pcie-mode dma`、helper cache、ステージングする GGUF source、その他の expert source のいずれも concurrent read の禁止条件にならないこと（`src/program/generate.cpp:12870-12892`, `include/strata/program/batch_read.hpp:30-53`）。
- 実際に concurrent read の処理へ進み、画像入力がないこと（`src/program/generate.cpp:12893`）。

Linux で `--aux-cpus` / `STRATA_AUX_CPUS` の配置機能が有効な場合、環境変数が未設定または非 0 でも、ここでの特別な host 外配置処理は一部スキップされます。代わりに、作成 thread の `pin_current_thread()` が aux CPU 計画に従います。Windows では aux CPU helper は no-op です。この変数による本番の追加配置処理は Linux 分岐にあり、Windows で host CPU affinity を一時的に設定する箇所は `STRATA_TEST_CONC_ON_HOST_CPU` によるテスト専用分岐です。

## 実行時の詳細

`conc_unpin` が true のとき、Linux で aux CPU 配置が無効なら、まず `release_host_inheritors()` を呼びます。これは host thread 自身と pool worker を除き、現在の affinity mask が host thread と完全一致する既存 thread を列挙し、host CPU と pool worker CPU を避ける mask へ移します。1つ以上移動した場合は stderr に `strata batch: %d threads that ran on the host thread's core moved off it, for reads beside the slots` と出します。CPU topology や affinity の取得・設定に失敗した場合などは、helper が移動数 0 を返すことがあります。

doorbell thread と各 prompt reader thread は `conc_thread_cpus` を呼びます。そこではまず `pin_current_thread()` を実行し、Linux で `conc_unpin` が true かつ aux CPU 配置が無効なら、続けて `place_off_host()` を試します。この helper は host CPU と pool worker CPU を避けた許可 CPU mask をその thread に設定します。`place_off_host()` の成否は呼び出し元でログ化されません。`conc_unpin` が false なら、この追加移動は行わず、作成元から継承した affinity を保ちます。

Windows では `STRATA_TEST_CONC_ON_HOST_CPU` が設定されていると、テスト経路が thread の CPU set を一時的に host thread と同じにし、`conc_unpin` が true なら空の CPU set を指定して解除します。このテスト分岐の開始時には `strata batch: test: the read's and the doorbell threads start on the host thread's %zu CPU set(s)...` を一度 stderr に出します。Windows の通常経路ではこの環境変数による host 外配置は行われません。

`STRATA_PIPED_CONCURRENT_UNPIN` 自体の値に関するログはありません。親の concurrent read 条件を満たさない場合や、画像入力がある場合は、設定値に関係なくこの変数の判定・配置処理まで到達しません。

根拠: `src/program/generate.cpp:12907-12950`; `include/strata/platform/aux_cpus.hpp:290-347,406-421`。

## 根拠

- 値の取得と static cache: `src/program/generate.cpp:12909-12912`。
- 適用経路と除外条件: `src/program/generate.cpp:11092-11094,12870-12893`; `include/strata/program/batch_read.hpp:30-53`。
- Linux の既存 thread の移動: `src/program/generate.cpp:12935-12940`; `include/strata/platform/aux_cpus.hpp:325-347`。
- 新規 thread の移動と Windows テスト分岐: `src/program/generate.cpp:12941-12950`; `include/strata/platform/aux_cpus.hpp:255-262,314-323,406-421`。
