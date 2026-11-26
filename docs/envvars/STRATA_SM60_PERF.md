# `STRATA_SM60_PERF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の全可視 GPU が compute capability 6.0（sm_60、Pascal GP100 / Tesla P100）であるときに、Strata が推奨する 7 個のスイッチを既定値として環境へ追加する機能の一括オフスイッチ。`STRATA_SM60_PERF` 自体は性能処理を直接切り替えず、`nv_default_env()` がこの値を見て sm_60 用テーブルを空にするか決める。テーブルが適用されるときの既定値は `STRATA_ADAPT_NOWAIT=1`、`STRATA_ADAPT_LAG=2`、`STRATA_SIDE_MIXER=2`、`STRATA_FUSE_WAIT=2`、`STRATA_B6_MMVQ_ROWS=1`、`STRATA_FUSE_DECODE=1`、`STRATA_GR_UP75=1`。各値はそれぞれの機能側で解釈される。`STRATA_FUSE_DECODE` による融合だけは `STRATA_EXPERIMENTAL_SM60` ビルドでコンパイルされた経路に限られる（`engine/src/core/nv_defaults.cpp:164-175`、`engine/include/strata/kernels/fuse_decode.hpp:2-14`）。

sm_60 のテーブル全体は bit-exact として記述されている。Strata のソースコメントは Tesla P100・IQ3_XXS・既定フラグで 8 組を測定し、7 スイッチの組み合わせが 8/8 組で +17.8%、identity gate が同一だったと報告している。これはソース内の測定記録であり、この調査で再測定した値ではない（`engine/src/core/nv_defaults.cpp:164-175`、`engine/include/strata/core/nv_defaults.hpp:1-7`）。

## 値と判定

`off()` は `std::getenv(name)` が null でなく、値の先頭 1 文字が `'0'` の場合だけ true を返す。文字列全体の parse や空白除去はしない（`engine/src/core/nv_defaults.cpp:14-18`）。

| 条件（build など） | unset | 設定時にテーブルを無効にする値 | テーブルを無効にしない例 |
|---|---|---|---|
| CUDA の sm_60 既定値判定 | 有効。テーブルを候補にする | 先頭文字が `0` の文字列（`0`、`00`、`0anything`） | 空文字、`1`、`true`、`false`、` 0`、`10` |

`true` / `false` の特別扱い、大文字小文字の変換、数値妥当性検査はない。明示的な空文字は設定済みだが、オフ判定にはならない。`STRATA_DEFAULTS=026` は sm_60 の分岐で調べられず、それだけではこのテーブルを止めない（`engine/src/core/nv_defaults.cpp:37-41,164-175`）。

テーブルを有効にする場合も、個々のスイッチがすでに環境に存在すればその値を保持する。個々のスイッチは値が `0` や空文字でも「ユーザー設定あり」と判定され、既定値で上書きされない（`engine/src/core/nv_defaults.cpp:222-234`）。

## 有効になる条件

- CUDA ビルドで `generate.cpp` の GPU 初期化経路に入り、`cudaGetDeviceCount()` が成功して 1 台以上の可視 GPU があること。HIP と Metal のビルドはこの処理のコンパイル対象外（`engine/src/program/generate.cpp:4421-4429`）。
- compute capability の取得に成功し、可視 GPU がすべて同じ compute capability であること。その値が major 6 / minor 0 のときに sm_60 テーブルが選ばれる。混在 GPU、属性取得失敗、GPU が 0 台または列挙失敗の場合は sm_60 既定値を適用しない。sm_60 用の個別 fallback はなく、この条件不成立だけを理由とする警告もない（`engine/src/program/generate.cpp:4427-4449`）。
- `STRATA_SM60_PERF` の値が前節の「テーブルを無効にする値」に該当しないこと。該当時は sm_60 テーブルを空で返す（`engine/src/core/nv_defaults.cpp:164-175`）。
- CLI 引数、モデルの種類やロード後状態による条件は、このテーブル適用箇所にはない。CUDA デバイス検出後、モデルのスイッチ利用より前に適用される（`engine/src/program/generate.cpp:4421-4449`、`engine/include/strata/core/nv_defaults.hpp:16-17`）。
- テーブル内のうち `STRATA_FUSE_DECODE=1` の融合を実行するには、加えて `STRATA_EXPERIMENTAL_SM60` が定義された build が必要。未定義ならそのスイッチが環境に設定されても、該当する fused 経路はコンパイルされない（`engine/include/strata/kernels/fuse_decode.hpp:2-14`、`engine/src/core/layer.cpp:261-272`）。

## 実行時の詳細

実行ファイルの `main` は CLI 引数処理後に CUDA デバイスを列挙し、全 GPU が同一アーキテクチャの場合 `apply_nv_defaults()` を呼ぶ。そこで `nv_default_env()` が `STRATA_SM60_PERF` を読み、sm_60 なら 7 個の既定値候補を返す。適用関数は各候補について `getenv(...) != nullptr` を確認し、未設定の名前だけを Windows では `_putenv_s`、それ以外では `setenv(..., 0)` で現在プロセスの環境に設定する。従って CLI 引数や別設定が `STRATA_SM60_PERF` を上書きする経路はなく、個々のスイッチに明示した環境値がそのスイッチの既定値より優先する（`engine/src/program/generate.cpp:4421-4449`、`engine/src/core/nv_defaults.cpp:222-234`）。

この一括判定は起動時の `apply_nv_defaults()` で行われるため、実行開始後に `STRATA_SM60_PERF` を変更しても既定値テーブルは再適用されない。適用された個々の変数は各機能が参照し、例えば `STRATA_ADAPT_NOWAIT` と `STRATA_ADAPT_LAG` は関数内 static に初回読み取り値を保持し、`STRATA_SIDE_MIXER` と `STRATA_FUSE_WAIT` も static に値を保持する。適応 tier が使われる経路では `ADAPT_NOWAIT=1` がコピー完了を待たず verify window を開始し、`ADAPT_LAG=2` がスワップ済み expert の採用を 2 window 遅らせる。ただし batch 経路、`--pipeline-windows`、peer tier は `ADAPT_LAG` の対象外。`SIDE_MIXER=2` は通常の verify window でミキサー関連処理を別 stream の枝に置き、batch window では `STRATA_BATCH_SIDE_MIXER=1` がない限りその枝を使わない。CUDA の `FUSE_WAIT=2` は plan の wait を copy に畳み込むが、CPU rows 側の wait は対象外（`engine/src/program/generate.cpp:2237-2250`、`engine/src/core/verify.cpp:272-293,1503-1515,507-522`）。

他のテーブル項目も独立した読み取り側に作用する。`B6_MMVQ_ROWS=1` は初回使用時に `atoi` で読み、対応する形式の multi-column 行カーネルを選択する（`engine/src/kernels/cuda/native_mmvq.cu:1247-1250,1408-1414`）。`FUSE_DECODE=1` は先頭文字が `1` の場合に有効になり、実験 build では活性値画像の量子化を一回の処理にまとめるなどの融合経路を選ぶ（`engine/include/strata/kernels/fuse_decode.hpp:9-14`、`engine/src/core/layer.cpp:261-272`）。`GR_UP75=1` は `atoi` の結果が非 0 なら有効だが、提示コード上の fused up 経路は `LR == 320` の条件も必要（`engine/src/kernels/cuda/fused_gr.cu:1558-1578`）。

これら下流スイッチの読み取り時期はそれぞれ異なり、対象環境変数の一括判定自体に cache はないものの、実行経路では起動時に一度だけ呼ばれる。下流の各機能が初回に値を cache する前に環境へ設定される設計である（`engine/include/strata/core/nv_defaults.hpp:16-17`、`engine/src/program/generate.cpp:4421-4449`）。

## ログと測定値

少なくとも一つのテーブル値を新たに設定した場合、stderr に次の形式で一行を出し、その後に今回設定した変数名を並べる。sm_60 では `strata: sm_60 (Pascal): N exact speed switches on by default (STRATA_SM60_PERF=0 turns them off; a switch you set is kept): ...`。7 個すべて未設定なら末尾の一覧は `ADAPT_NOWAIT ADAPT_LAG SIDE_MIXER FUSE_WAIT B6_MMVQ_ROWS FUSE_DECODE GR_UP75`。ユーザーが全スイッチを明示していて新規設定がない場合、この行は出ない。`STRATA_SM60_PERF` でテーブルを無効にした場合の専用警告・エラーや終了処理はなく、テーブルを空で返す（`engine/src/core/nv_defaults.cpp:164-175,222-255`）。

ソースの測定コメントは Tesla P100・IQ3_XXS・既定フラグで 8 組を測り、7 スイッチの組み合わせで +17.8%（8/8 組）、identity gate は同一と記録している。identity gate の条件はコメントにある 10 prompts と exact prompt checks 4K / 20K。これらは測定記録であり、環境やモデル一般に対する性能保証ではない（`engine/src/core/nv_defaults.cpp:164-175`、`engine/include/strata/core/nv_defaults.hpp:1-7`）。

## 根拠

- 判定と sm_60 テーブル: `engine/src/core/nv_defaults.cpp:14-18,164-175`
- 起動時のデバイス条件・呼び出し: `engine/src/program/generate.cpp:4421-4449`
- 個々の環境値を保持して既定値を設定する処理とログ: `engine/src/core/nv_defaults.cpp:222-255`
- sm_60 テーブルの適用時期と対象 GPU 条件: `engine/include/strata/core/nv_defaults.hpp:16-17`
- fused decode の build 条件と消費側: `engine/include/strata/kernels/fuse_decode.hpp:2-14`、`engine/src/core/layer.cpp:261-272`
- ソースに記録された測定条件: `engine/include/strata/core/nv_defaults.hpp:1-7`、`engine/src/core/nv_defaults.cpp:164-175`
