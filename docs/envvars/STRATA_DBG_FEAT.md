# `STRATA_DBG_FEAT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP エンジンの MoE prefill で、ルーターが選んだ expert ID と重みを chunk ごとにファイルへ書き出す研究用フック。`STRATA_DBG_FEAT` 自体はルーティングを変更しない。`STRATA_DBG_ROUTE_OVERRIDE` も同時に設定されている場合、ダンプ後に別ファイルのルーティングを適用する処理が走る。実装は `Prefill::run_impl` の MoE 層処理にあり、Metal / SYCL 側にこの名前の読み取りはない（`engine/src/prefill/prefill.cpp:4214-4220, 5577-5595, 5625-5645`; CUDA/HIP 用ターゲットの登録: `engine/cmake/strata_gpu_engine.cmake:482`）。

また、layer-major prefill の準備時にも設定有無を調べる。layer-major が選択されている実行ではこのデバッグフックを理由に layer-major を辞退し、通常の `run_impl` 経路に進む（`engine/src/prefill/prefill.cpp:8205-8209, 9657-9705`）。

## 値と判定

値を真偽値として parse せず、`std::getenv` が null かどうかだけで有効性を判定する。ダンプ側は取得した文字列全体を `std::fopen(path, "wb")` のパスとして使う。空白除去、大文字小文字変換、数値・真偽値変換はない（`engine/src/prefill/prefill.cpp:5591-5595, 8205-8209`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP の chunk-major MoE prefill | `feat_path == nullptr`。この変数による出力なし。ほかの debug env が設定されれば共通ブロック自体は動く | `dump.bin`、`1`、`true` など、文字列がそのまま出力パスになる。`getenv` が非 null ならフックを有効扱い | `0`、`false` もファイル名として扱われるため、値としては無効にならない。明示的な無効値はない |
| layer-major の可否判定 | この変数単独では辞退理由にならない | 空文字を含め、環境変数が存在すれば辞退条件に該当 | unset のみ |

空文字も `getenv` は非 null を返すため、ダンプ機能が有効扱いになり、layer-major も辞退対象になる。ダンプ側は空文字列をパスとして `fopen` に渡す。ファイルを開けなかった場合 `ff` は null になり、書き込みは行われないが、明示的なエラー処理はない（`engine/src/prefill/prefill.cpp:5592-5595, 5625-5640`）。`fopen` の成功可否以外に、値の構文・長さ・境界を検証するコードはない。

## 有効になる条件

- CUDA/HIP エンジンで、`Prefill::run_impl` が MoE 層を処理すること。ダンプはルーター計算と `route(...)` の後に実行されるため、MoE 層を通らない処理では出力されない（`engine/src/prefill/prefill.cpp:5577-5595`）。
- 出力ファイルを開けるパスであること。開けない場合もエラーを返さず、ダンプ部分だけが書き込みを行わない（`engine/src/prefill/prefill.cpp:5595, 5625-5640`）。
- `STRATA_DBG_FEAT_LAYERS`（別変数）が選ぶ層では router 入力 hidden state も追加出力する。未設定時のリストは `3,4,15,16,27,28,39,40`。設定時はカンマ区切りごとに `atoi` し、0〜63 の値を有効にするため、空要素や数値で始まらない要素は `atoi` の結果 0 として扱われる。64 以上・負値は無視され、層選択には `l & 63` が使われる（`engine/src/prefill/prefill.cpp:5596-5603, 5631-5638`）。この変数が空文字ならリストが空になり、hidden state は追加されない。
- `STRATA_DBG_ROUTE_OVERRIDE`（別変数）が同時にある場合、同じフック内で override ファイルも読み込む。`STRATA_DBG_FEAT` のダンプは override 適用より前に書かれるため、記録される ID と重みは上書き前のルーター出力。override は対象の `(layer, pos)` レコードがあり、ID 配列長が `T * K` と一致するときだけ適用される（`engine/src/prefill/prefill.cpp:5592-5595, 5606-5620, 5625-5645`）。
- layer-major prefill が無効、またはその準備処理に入らない経路では、`8206` のチェックによる経路変更や辞退ログは発生しない。layer-major の設定自体は `STRATA_PREFILL_LAYER_MAJOR` などで解決される（`engine/src/prefill/prefill.cpp:9652-9662`）。

## 実行時の詳細

`Prefill::lm_prepare` は layer-major の準備時に `getenv("STRATA_DBG_FEAT")` の有無をその都度確認し、設定されていれば `why = "a routing or row debug dump"` を返して準備を辞退する。layer-major が有効な場合、辞退後は `run_impl` が呼ばれる（`engine/src/prefill/prefill.cpp:8166-8169, 8205-8209, 9677-9705`）。

ダンプ側の `feat_path` と `ff` は関数内 `static` で、最初の MoE 層処理時に一度だけ環境値を読み、ファイルを `"wb"`（新規作成または切り詰め）で開く。`STRATA_DBG_FEAT_LAYERS` の解析、層ごとの `posl` カウンターも static で初回に確定・初期化される。したがって、通常の起動時環境を前提にすると、プロセス中の環境変更はダンプ先・層選択へ反映されない。`lm_prepare` 側の有無判定は static cache ではない（`engine/src/prefill/prefill.cpp:5591-5604, 8205-8209`）。

各 MoE 層・chunk で、フックは GPU stream を同期し、ID と重みをホストへコピーする。ファイルには 4 個の `int32`（実層番号、フック内の層別累積位置、chunk 行数 `T`、hidden state 有無フラグ）に続き、`T*K` 個の `uint16` ID と `T*K` 個の bf16 重みを書き込む。選択層ではさらに `T*N` 個の bf16 router 入力 hidden state を書く。層別位置はフック開始後に 0 から始まり、chunk ごとに `T` 増える（`engine/src/prefill/prefill.cpp:5604, 5622-5638`）。

このフックは同期・device-to-host copy・ファイル I/O を加えるが、`STRATA_DBG_FEAT` の処理自体は `m.ids` / `m.w` を書き換えない。ルーティングを変更するのは別の `STRATA_DBG_ROUTE_OVERRIDE` 分岐である（`engine/src/prefill/prefill.cpp:5624-5645`）。CLI 引数やサーバーモードによる値の上書きはこの読み取り箇所にはない。

## ログと測定値

layer-major が設定・選択されている場合、辞退理由が変わったときに stderr へ `strata prefill: layer-major off for this prompt: a routing or row debug dump` と出る。同じ理由の連続時は抑制され、長い prompt の辞退が続く場合は 16 回ごとに `strata prefill: layer-major still off, ...` の継続ログが出る。layer-major 自体が選択されていない場合、この理由ログは出ない（`engine/src/prefill/prefill.cpp:9694-9703`）。

出力ファイルの open / write 失敗を示す専用ログ、終了・エラー返却は確認できない。ファイル書き込みの戻り値も検査されていない（`engine/src/prefill/prefill.cpp:5595, 5632-5638`）。`docs/DETAILS.md` にこの変数の測定値・性能比較の記載は見つからないため、測定値は記載しない。

## 根拠

- `engine/src/prefill/prefill.cpp:5577-5595` — MoE ルーティング後のフック、環境変数読み取り、ファイル open。
- `engine/src/prefill/prefill.cpp:5596-5604` — 関連層リストの parse と static cache。
- `engine/src/prefill/prefill.cpp:5622-5645` — 同期、ダンプ形式、override の適用順。
- `engine/src/prefill/prefill.cpp:8166-8209` — layer-major 準備時の適用条件と辞退理由。
- `engine/src/prefill/prefill.cpp:9652-9705` — layer-major 選択・辞退ログ・chunk-major `run_impl` への経路。
- `engine/cmake/strata_gpu_engine.cmake:482` — CUDA/HIP GPU engine のソース登録。
