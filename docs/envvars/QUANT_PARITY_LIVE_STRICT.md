# `QUANT_PARITY_LIVE_STRICT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

この変数は製品エンジンの実行設定ではなく、テスト専用実行ファイル `quant_parity` の比較方針を切り替える。golden reference が使える標準実行では、Strata の量子化結果とリンク中の `ggml-cpu` の結果が異なったとき、既定では差分を情報として表示し、非空かつ文字列 `0` 以外の値を設定するとその差分を失敗として数える。golden reference による leg 1 の判定はこの変数で変わらない。`quant_parity` は `STRATA_BUILD_TESTS` が有効で、かつ `STRATA_QUANT_NO_GGML` でない量子化レイヤーの構成時にだけ作られる（`engine/cmake/backends/quant.cmake:108-139`）。

## 値と判定

`main` で `std::getenv` を一度呼び、値を数値や真偽値として parse せず、unset/null、空文字、文字列全体が `"0"` かどうかを判定する（`engine/tests/quant/quant_parity.cpp:683-686`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| golden leg 1 が実行される標準比較（golden がロードでき、`--rows` が既定値 24、`--write-golden` なし） | leg 2 は情報扱い | 空でなく文字列全体が `"0"` ではない任意の値（例: `1`, `true`, `00`, `0anything`, 空白） | unset、空文字、文字列全体が `0` のみ |
| golden leg 1 が実行されない比較 | strict は無条件で有効 | 値にかかわらず strict | なし |

比較は大文字小文字や空白を正規化しない。`"0 "` や `" 0"` は `"0"` と異なるため strict 扱いになる。`--rows` の引数は別途 `atoi` で変換され、golden leg の有無に影響するが、環境変数の値判定には影響しない（`engine/tests/quant/quant_parity.cpp:637-686`）。

## 有効になる条件

- `quant_parity` 自体がビルドされていること。量子化レイヤーの CMake は `STRATA_BUILD_TESTS` ブロック内で、さらに `NOT STRATA_QUANT_NO_GGML` のときに `quant_parity` を登録する（`engine/cmake/backends/quant.cmake:108-139`）。標準エンジン構成では tests off なら ggml oracle test は作られず、ggml なしの構成も `STRATA_QUANT_NO_GGML` を設定する（`engine/CMakeLists.txt:727-736, 890-894`）。
- 起動後に ARM64 の linked `ggml-cpu` が dot-product 拡張なしと判定された場合は、比較と環境変数読み取りの前に `SKIPPED` として正常終了する（`engine/tests/quant/quant_parity.cpp:670-686`）。
- golden 比較が使えない（golden 未ロード、`--rows` が 24 以外、または `--write-golden` 指定）と `g_live_strict` は環境変数を見ずに true になる。その経路ではこの変数で挙動を切り替えられない（`engine/tests/quant/quant_parity.cpp:637-647, 683-686`）。
- ARM64 で linked `ggml-cpu` が SVE を持つ場合は `g_info_only` も true になる。strict でも差分は `g_fail` に加算されるが、最終結果は `DIFFERENCES (information only)` と表示され、終了コードは 0 に抑えられる（`engine/tests/quant/quant_parity.cpp:678-681, 151-155, 788-789`）。
- `--type` は golden leg の判定式に含まれず、`--rows 24` など他の条件が揃えば strict 判定は有効。ただし `--type` 指定時は未実行 golden group の不足チェックを行わない（`engine/tests/quant/quant_parity.cpp:642-648, 683-686, 779-781`）。
- `--regen-check` と `--write-golden` は比較後に独自の早期終了経路を持つ。strict は比較中の差分カウンター／`FAIL` 出力には反映されるが、これらの経路の終了コードは golden 再生成一致またはファイル書き込みの結果で決まる（`engine/tests/quant/quant_parity.cpp:720-735, 737-789`）。

## 実行時の詳細

`main` は引数処理、digest self-test、`--regen-check` の実行可否判定、`ggml_cpu_init()` と ARM64 の dot-product 判定の後に golden file を読み、`g_golden_leg` と環境値から `g_live_strict` を設定する（`engine/tests/quant/quant_parity.cpp:637-686`）。値はプロセス実行中に一度だけ取得し、関数内キャッシュや後続の再読み込みはない。起動後の環境変更は反映されない。

差分ごとに `live_diff` は `g_live_diff` を増やす。strict の場合は `fail` を呼び、差分を `g_fail` に含める。strict でない場合は最初の 10 件まで `live: <what>: <detail>` を stdout に出す。strict 時は `FAIL <what>: <detail>` を最大 40 件出力する。標準の golden 実行では leg 2 の集計を出し、失敗があれば `quant_parity: ... -> FAIL` と終了コード 1、なければ `... -> PASS` と 0 になる（`engine/tests/quant/quant_parity.cpp:145-155, 779-789`）。

同梱の `engine/tests/quant/run_oracle.sh` はこの名前を特別に parse せず、ビルドした `quant_parity` を実行する。シェルは起動環境を引き継ぐため、変数を設定して script を呼ぶ場合は子の `quant_parity` に届く（`engine/tests/quant/run_oracle.sh:6-8, 32-40`）。

## ログと測定値

標準 golden 実行では開始時に leg 2 が `FATAL, QUANT_PARITY_LIVE_STRICT` か `information` かを表示する（`engine/tests/quant/quant_parity.cpp:695-697`）。終了前の集計は `quant_parity: leg 2 (FATAL|information): ...` と `quant_parity: ... failures -> FAIL|PASS` の形式（同ファイル `:782-789`）。SVE の情報専用経路では末尾が `DIFFERENCES (information only)` となり、strict の有無にかかわらず終了コード 0（同ファイル `:678-681, 788-789`）。この環境変数に関する測定値は確認できなかった。

## 根拠

- `engine/tests/quant/quant_parity.cpp:137-155, 637-686, 779-789` — strict 状態、読み取り・比較・差分処理・終了結果。
- `engine/cmake/backends/quant.cmake:108-139` — test / ggml 条件下での `quant_parity` ターゲット登録。
- `engine/CMakeLists.txt:727-736, 890-894` — 通常エンジンおよび ggml なしの構成条件。
- `engine/tests/quant/run_oracle.sh:6-8, 32-40` — テスト runner の対象と子プロセス起動。
