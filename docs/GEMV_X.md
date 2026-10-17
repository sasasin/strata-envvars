# `GEMV_X`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。調査範囲は Strata 所有ソース。

## 役割

`GEMV_X` は通常の Strata 実行時設定ではなく、Metal の dense GEMV parity/benchmark プログラム `metal/tests/gemv_parity.cpp` が `gemvx_*` カーネル候補を測るためのテスト用切替です。調査対象 commit で完全一致検索した読み取り箇所はこの一箇所だけです。本番の推論経路から読むコードは見つかりませんでした。

## 値と判定

| 状態 | `gx` の値 | 動作 |
|---|---:|---|
| 未設定 | `false` | 通常の `gemv_*` カーネル構成 `kCfgs` をベンチマークする |
| 設定あり（空文字を含む） | `true` | `gemvx_*` 用の固定構成リストをベンチマークする |

値の内容、数値、大小文字は調べません。判定は `std::getenv("GEMV_X") != nullptr` のみなので、`GEMV_X=0` や `GEMV_X=false` も設定されていれば有効です。読み取りはベンチマーク内の `nt` ループごとに行われ、static cache はありません。

## 有効になる条件

この分岐は `gemv_parity` のベンチマーク経路にあります。通常の parity 経路は `--bench` がないと先に終了するため、`GEMV_X` は `--bench`（必要に応じて `--one` などの引数）でベンチマーク部分に入ったときだけ参照されます。Metal テスト用ソースのため、CUDA/HIP/SYCL や通常の Strata 実行ファイルに対する設定ではありません。

設定時は固定された 12 個の `(L,R,S,K)` 候補を使い、`cfg_ok`、`--all` と入力形状によるフィルターを適用します。さらに計算した threadgroup memory 要求 `tgm` が 32768 byte を超える候補は除外します。これらの条件を通った候補について、カーネル名を `gemvx_<type>_<L>_<R>_<S>` とし、dispatch に `tg_mem = tgm` を設定します。無効な候補の扱いや測定失敗時の詳細は `GEMV_X` 自身による処理ではなく、共通のテストランタイムに委ねられます。

## 実行時の詳細

`GEMV_X` が変えるのはこのテストプログラムが選ぶカーネル候補、カーネル名、および threadgroup memory の要求です。各候補について warm-up 後に 5 回計測し、その中央値を出力します。`--one` を使った場合は候補ごとの時間も表示されます。環境変数の切替自体について特別な警告やログは出しません。変数はテストプログラムの結果に影響し得ますが、製品の GEMV 選択や推論挙動を制御する根拠は見つかりませんでした。

## 根拠

- `metal/tests/gemv_parity.cpp:1-6` — parity/benchmark 用プログラムと起動引数の説明。
- `metal/tests/gemv_parity.cpp:164-165,243-245` — 通常の parity 経路は benchmark 経路より先に終了し、以降が bench 処理。
- `metal/tests/gemv_parity.cpp:287-315` — 環境変数の有無判定、候補切替、候補フィルター、カーネル名、threadgroup memory の dispatch 設定。
- 調査対象リポジトリ全体で `GEMV_X` の直接参照は上記一箇所のみ。`docs/DETAILS.md` にこの名前の説明はなく、追加の適用条件や測定結果は確認できませんでした。
