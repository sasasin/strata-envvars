# `STRATA_QSA_DUMP_LAYER`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA/HIP 側の prompt prefill にある QSA 選択結果の診断ダンプで、記録する QSA layer を絞ります。この変数だけではダンプを開始しません。`STRATA_QSA_DUMP` にファイルパスが設定されているときにだけ判定され、負の値なら全 QSA layer、0 以上ならその番号の layer だけを対象にします。通常の QSA 選択や attention の計算方法は切り替えず、診断データの出力範囲だけを変えます。

## 値と判定

値は `std::atoi` で整数に変換され、文字列全体の検証はありません。未設定時の既定値は `-1` です。

| 設定値 | 判定と対象 |
|---|---|
| 未設定 | `-1`。全 QSA layer を対象にする |
| 負の整数 | 全 QSA layer を対象にする |
| `0` 以上の整数 | 変換後の番号と一致する QSA layer だけを対象にする。番号は 0 始まり |
| 空文字・数値に変換できない文字列 | `atoi` の結果は `0` となり、QSA layer 0 だけを対象にする |
| 数字の後ろに文字が続く値 | 数字として読める先頭部分が使われる。例: `2abc` は layer 2、`-1x` は全 layer |

先頭の空白や符号も `atoi` の整数変換規則に従います。範囲外整数に対する `atoi` の結果はこの実装で保証されません。

## 有効になる条件

- `STRATA_QSA_DUMP` が未設定でないこと。空文字も「設定あり」としてダンプ処理に入り、ファイルを開こうとしますが、空パスへの `fopen` は失敗します。
- QSA を含むモデルの prompt prefill が実行され、QSA 選択処理まで到達すること。
- 現在の chunk がダンプ範囲内であること。別変数 `STRATA_QSA_DUMP_LAST` による条件 `p0 + T > pos0 + n - last` も満たす必要があります。同変数の既定値は 4096 です。
- `STRATA_QSA_DUMP` で指定したファイルを追記モードで開けること。開けなかった場合、この処理はエラーや警告を出さず、レコードを書きません。

この環境変数の読み取り箇所は `src/prefill/prefill.cpp` の一つです。CMake では同ファイルが `strata_prefill` に含まれています。SYCL 移植版の `sycl/src/prefill/prefill.cpp` にある同種の QSA ダンプは layer 番号による絞り込みを行わないため、同版でこの変数を設定しても効果はありません。

## 実行時の詳細

ダンプブロック内で `STRATA_QSA_DUMP` のファイルポインターと `STRATA_QSA_DUMP_LAYER` の整数値を block-scope `static` として保持します。初回評価はダンプブロックに初めて到達したときに行われ、`STRATA_QSA_DUMP` が null ならその null が保持されます。その後の prefill 呼び出しでも値は再評価されないため、最初の通過時に `STRATA_QSA_DUMP` が unset だった場合、後から設定してもこのプロセスではダンプが始まりません。また `STRATA_QSA_DUMP_LAYER` も初回評価後に変更しても layer 選択は更新されません。

`qsa_index` は QSA layer ごとに 0 から始まり、処理後に 1 増えます。フィルターを通った chunk では `m.sel_ids` をホストへコピーして stream を同期し、ファイルを `ab` で開いて、`int32` 4個のヘッダー `{qsa layer, p0, T, cap}` と `T * cap` 個の選択 cell ID を追記します。`STRATA_QSA_DUMP_STEPS` も設定されていれば、後続に step 情報も追記します。選択範囲は `STRATA_QSA_DUMP_LAST` によって制限されます。

通常利用者向けの推論設定ではなく、QSA 選択結果をファイルに記録する調査用フックです。選択 chunk では device-to-host コピーと stream 同期が追加されます。実装は `fopen` 失敗を報告しません。

## 根拠

- `src/prefill/prefill.cpp:2640-2641,3041-3044,3231-3255,3278` — QSA index の初期化・増分、dump の条件、整数変換、ファイル追記。
- `CMakeLists.txt:675-685` — `src/prefill/prefill.cpp` が `strata_prefill` に含まれること。
- `sycl/src/prefill/prefill.cpp:3128-3154` — SYCL 側の対応 dump は layer filter を含まない。

