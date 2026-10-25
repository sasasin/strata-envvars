# `STRATA_PIPELINE_DEBUG`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows` の試験・調整・診断用 `STRATA_PIPELINE_*` 環境変数を読み取れるようにするゲートです。この変数自体は pipeline windows を有効にせず、pipeline の実行選択は CLI の `--pipeline-windows` などが担います。ゲートが閉じている場合、共通 helper `pipe_dbg_env()` は個々の環境変数を読まず `nullptr` を返すため、呼び出し側の既定値が使われます。

## 値と判定

値全体の parse や数値変換はせず、`getenv()` が返す文字列の先頭だけを判定します。

| 環境変数の状態・値 | ゲート |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| 先頭文字が `0`（例: `0`, `0abc`） | OFF |
| 先頭文字が `0` 以外（例: `1`, `true`, `false`, `2`, 空白から始まる値） | ON |

したがって `false` も ON です。大文字小文字、空白、残りの文字列、数値としての妥当性は検査されません。判定結果は `pipe_dbg_env()` 内の関数ローカル `static const bool` に保存され、各実装で最初に helper が呼ばれた後の環境変更では再評価されません。

根拠: `src/program/generate.cpp:254-257`、`sycl/src/program/generate.cpp:295-298`。

## 有効になる条件

ゲートが ON でも、pipeline の機能は `--pipeline-windows` などで対応する pipeline 経路が実行される場合に限って使われます。たとえば `STRATA_PIPELINE_SNAP_OVERLAP` は pipeline が有効で `--pipeline-windows >= 2` の場合に参照されます。その他の設定の参照箇所も pipelined prompt/decode の処理内にあります。

ソースでこの helper を通じてゲートされる設定は、CUDA/HIP 側の `STRATA_PIPELINE_SNAP_OVERLAP`、`THETA`、`FORCE_MISS`、`SWITCH`、`LOG`、`TRACE`、`DOOM_SKIP`、`LOOKUP_PON`、`PRESTAGE`、`AGREE`、`SPEC_DEPTH` と、SYCL 側の同名設定（`SPEC_DEPTH` の読み取りは CUDA/HIP 側にあります）です。これらの具体的な値の扱いは各設定の読み取り側で別に決まります。例として、`THETA` は未設定時 `0.2`、`FORCE_MISS` は未設定時 `0`、`LOOKUP_PON` は未設定時 `0.75` です。ゲートが OFF の場合、これらは未設定相当となり、各箇所の既定動作になります。

根拠: `src/program/generate.cpp:7625-7628,10534-10554,11205-11206,11261-11270,11275-11279,11394-11400,11444-11450,11603-11608`、`sycl/src/program/generate.cpp:7238-7243,9849-9870,10455-10459,10543-10552,10557-10562,10714-10719,10763-10770`。

## 実行時の詳細

ゲートが開くと、呼び出し側が名前を渡した pipeline 用環境変数を `getenv(name)` で取得します。環境変数を読み取っているだけの診断設定（`STRATA_PIPELINE_LOG`、`STRATA_PIPELINE_TRACE`）と、試験・調整動作（推測窓の閾値、強制 miss、pipeline 切替ファイル、snapshot overlap など）の両方がこのゲートの対象です。`STRATA_PIPELINE_SWITCH` は pipeline 経路内で指定ファイルを読み、`pw`、`theta`、`force_miss`、`short_read` を上書きします。

CUDA/HIP 側と SYCL 側にそれぞれ同等の helper があります。ソース上、この環境変数を読む箇所はこの二つの helper のみで、設定値を子プロセスへ転送する処理は確認できませんでした。

`docs/MULTI_GPU.md` も、pipeline の tuning/test 変数が `STRATA_PIPELINE_DEBUG=1` のときだけ読まれると説明しています。ただし実装は厳密な `=1` 比較ではなく、上記の先頭文字判定です。

## 根拠

- `src/program/generate.cpp:254-257` — CUDA/HIP 側 helper と値判定。
- `sycl/src/program/generate.cpp:295-298` — SYCL 側 helper と同じ値判定。
- `src/program/generate.cpp:7625-7628`、`sycl/src/program/generate.cpp:7238-7243` — snapshot overlap 設定の pipeline 条件。
- `src/program/generate.cpp:10531-10554`、`sycl/src/program/generate.cpp:9846-9870` —閾値、強制 miss、switch file の読み取りと switch file による値の適用。
- `src/program/generate.cpp:11205-11206,11261-11279,11394-11450,11603-11608`、`sycl/src/program/generate.cpp:10455-10459,10543-10562,10714-10719,10763-10770` — log、trace、doom skip、lookup、prestage、agree、speculation depth の参照。
- `docs/MULTI_GPU.md:311-313` — tuning/test 変数についての文書説明。
