# `STRATA_KVA_CAPTURE_FP32`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `main...origin/main` で、未コミット変更は表示されませんでした。外部ライブラリの環境変数は対象外です。

## 役割

`STRATA_KVA_CAPTURE` で有効にした KVA 入力キャプチャのファイル形式を選びます。フラグが有効なら各記録を 32-bit float（fp32）で保存し、無効なら bf16 に丸めて保存します。fp32 は parity run 用として実装コメントに記載されています。

この変数だけではキャプチャは始まりません。`STRATA_KVA_CAPTURE` に空でないディレクトリが指定されているときだけ本変数を読み、その設定をキャプチャ用 tap に渡します。キャプチャ中は近似 KVA を適用せず、通常の prefill を実行しながら、split 以降の層へ入る残差入力を記録します。

## 値と判定

`kva_env_flag` は値を数値や真偽値として parse せず、設定値の先頭文字だけを判定します。未設定または空文字は既定値の `false` です。

| `STRATA_KVA_CAPTURE_FP32` | 判定 |
|---|---|
| 未設定、または空文字 | 無効（bf16 記録） |
| 空でない値の先頭文字が `0` | 無効（bf16 記録）。例: `0`, `0abc` |
| 空でない値の先頭文字が `0` 以外 | 有効（fp32 記録）。例: `1`, `true`, `false`, `2`, ` 0` |

大文字小文字、空白、文字列全体の妥当性は検査しません。従って `false` も先頭が `f` のため有効です。数値範囲や無効値時の警告・fallback parse はありません。無効値でも単に bf16 側になります。

なお、`STRATA_KVA_CAPTURE` が未設定または空文字の場合、`STRATA_KVA_CAPTURE_FP32` の値は構成に反映されず、その環境値は読み取られません（`include/strata/prefill/kva.hpp:143-167`）。

## 有効になる条件

- `STRATA_KVA_CAPTURE` が空でない出力先ディレクトリを指定すること。CLI 引数や設定ファイルによるこの変数の上書きは実装にありません。
- prompt の層ループで、全層を処理する経路であること。`kva_cap_layer` は `LB == 0`、`LE < 0` または全層終端、かつ `l >= kva_split` のときだけ true です。分割された層範囲ではキャプチャしません（`src/prefill/prefill.cpp:3621-3629`）。
- KVA capture tap が使われる prefill 実装を含むビルドであること。共通の `strata_prefill` target は `prefill.cpp` を含み、HIP build では HIP 用 GEMM 実装も追加されます（`CMakeLists.txt:819-825`）。本変数自体に OS 判定や backend 別の値判定はありません。
- `STRATA_KVA=1` はキャプチャの必須条件ではありません。むしろ `KvaConfig::decline()` は `capture` を理由に近似経路を断り、記録時のコメントも capture run は通常の full read としています（`include/strata/prefill/kva.hpp:108-114`; `src/prefill/prefill.cpp:3689-3694`）。他の KVA 設定やモデル形状はこの形式選択を上書きしません。

## 実行時の詳細

`kva_config()` は `kva_config_from_env()` の結果を function-local `static const KvaConfig` に保持します。従って設定はプロセス内で初回評価時に一度読み取られ、後からプロセス環境を変えても再評価されません。設定解析は generate 側の初期化と prefill から呼ばれます（`include/strata/prefill/kva.hpp:149-195`; `src/program/generate.cpp:6263-6265`; `src/prefill/prefill.cpp:2947-2955`）。

キャプチャが有効なら、prefill は process-wide の `KvaTap` を初期化します。cold read の開始時にはファイルを閉じ、層ごとの次の位置を 0 に戻します。層に初めて到達したとき `<capture_dir>/L<layer>.bin` を `wb` で開くため、新しい prompt の記録は既存ファイルを上書きします。各対象層では残差 `R` を device から host にコピーして同期し、fp32 の場合は float 4-byte 要素列をそのまま書きます。bf16 の場合は 2-byte に丸めて書きます（`src/prefill/prefill.cpp:2820-2824,2834-2886,2967-2972`）。

対象層の開始時点の `R` が記録対象です。一層につき `L<layer>.bin` 一つで、位置順の行を保存します。読み取り処理は別の `STRATA_KVA_ORACLE_FP32` の設定を参照するため、capture 側の形式と oracle 側の形式は自動連動しません（`src/prefill/prefill.cpp:2889-2925`; `include/strata/prefill/kva.hpp:163-171`）。

成功時、stderr に `strata prefill: KVA off (capture): ... , capturing the late layers' inputs` を含む行が出ます。失敗時、層範囲外・位置順不一致・device-to-host copy/sync 失敗・ファイルを開けない場合は `KvaTap::write` がエラー文字列を設定し、prefill を `false` で返します。ソースには `fwrite` と `fflush` の戻り値を検査する分岐はありません（`src/prefill/prefill.cpp:2852-2886,3689-3692,5820-5831`）。

## 根拠

- 候補名の実コード参照は `include/strata/prefill/kva.hpp:80,166` のみです。他の一致は `src/prefill/prefill.cpp:2822` のコメント、`docs/KVA.md:120,172` の説明・例、およびテスト用環境変数退避リスト `src/prefill/kva_test.cpp:33` です。テスト・コメント・文書だけで挙動を判断せず、実装の helper、呼び出し、出力処理まで追跡しました。
- 共通 flag helper の判定と capture 条件: `include/strata/prefill/kva.hpp:143-167`。
- capture tap の形式、ファイル名、書き込み・失敗条件: `src/prefill/prefill.cpp:2820-2887`。
- capture 対象層、完全 prefill 範囲での制限、呼び出し: `src/prefill/prefill.cpp:3621-3629,3689-3692`。
- プロセス内 cache、capture 起動とログ: `include/strata/prefill/kva.hpp:191-195`; `src/prefill/prefill.cpp:2947-2972,5820-5831`。
- 関連説明: `docs/KVA.md:108-123,169-178`。表と使用例は、実装の「capture 時だけ FP32 flag を読む」「capture 時の read は exact」という動作と整合します。
