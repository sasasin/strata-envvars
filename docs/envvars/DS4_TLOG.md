# `DS4_TLOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 engine の Metal build で、GPU のイベント計測とは別に、host 側で layer 処理区間の経過時間を集計する診断ログを有効にします。モデル計算の選択や出力を切り替える環境変数ではありません。Strata の Mac 向け資料でも、既定 OFF の診断項目として `DS4_TLOG=1` を案内しています（`docs/DEEPSEEK_MAC.md:97-98`）。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 設定あり | 有効。値の内容は検査しないため、`1` 以外や空文字でも有効 |

Metal build の `ds4_dbg(name)` は `std::getenv(name) != nullptr` を返します。`DS4_TLOG` はこの helper に動的に名前を渡しており、`prof_mark()` が呼ばれるたびに設定有無を読みます。環境値の数値変換、範囲検査、空文字の特別扱い、優先順位や fallback はありません。診断値は CLI 引数や他の環境変数から上書きされません（`src/dsv41/ds4_launch.h:30-36`, `src/dsv41/ds4_model.cu:1361-1363`）。

## 有効になる条件

この環境参照がコンパイルされるのは `STRATA_METAL` build のみです。それ以外の build では helper が常に `false` を返すため、`DS4_TLOG` を設定してもこのログは有効になりません（`src/dsv41/ds4_launch.h:30-36`）。この実装は `src/dsv41` の DeepSeek V4.1 engine に属します。

Metal build でも、モデルの forward 処理で `prof_mark()` に到達する必要があります。該当関数は layer の処理区間で呼ばれます（例: `src/dsv41/ds4_model.cu:10007,10287,10358-10361`）。通常の CUDA GPU profiling (`DS4_PROF`) の有効状態や decode-window 条件を確認する前に、`DS4_TLOG` の集計処理を実行するため、これらの条件は TLOG の有効条件ではありません（`src/dsv41/ds4_model.cu:1361-1380`）。

## 実行時の詳細

最初に `prof_mark()` で環境変数が設定済みと確認されたとき、関数内 static の時刻・累積値・layer 数を使い始め、終了時出力用の `std::atexit` handler を一度登録します。各有効な計測点で host の単調時計を読み、前回の計測点からの時間を 5 区分（`attn`, `moe_pre`, `gate_up`, `cpu_wait`, `down+post`）へ加算します。stage 3 の計測点ごとに layer 数を加算します（`src/dsv41/ds4_model.cu:1361-1378`）。

正常なプロセス終了時、登録済み handler は標準エラーへ `tlog: ... | host ms: ...` の1行を出力します。計測点に一度も到達しない場合、または有効な環境値の状態で `prof_mark()` が呼ばれなければ handler は登録されず、TLOG 行も出ません。ここに失敗時の警告や終了コード変更は実装されていません（`src/dsv41/ds4_model.cu:1364-1370`）。

環境値の判定自体は static cache されず各計測点で再評価されますが、集計カウンターと handler 登録状態は関数内 static でプロセス中保持されます。通常の子プロセスへの転送や、CLI による設定処理はこの箇所にはありません（`src/dsv41/ds4_model.cu:1361-1369`）。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — `ds4_dbg` の Metal / 非 Metal build 別実装。非 Metal は常に false。
- `src/dsv41/ds4_model.cu:1361-1378` — `DS4_TLOG` の判定、host 時刻集計、終了時ログ登録と出力内容。
- `src/dsv41/ds4_model.cu:10007,10287,10358-10361` — forward の layer 処理からの計測点呼び出し例。
- `docs/DEEPSEEK_MAC.md:97-98` — Mac engine の診断項目として既定 OFF で案内。
