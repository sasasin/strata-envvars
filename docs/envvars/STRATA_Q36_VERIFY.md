# `STRATA_Q36_VERIFY`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Qwen3.6-35B-A3B 専用 engine の decode 用高速 CUDA/HIP kernel の一部について、新 kernel と従来 kernel を同じ実 activation で実行し、結果を bit 単位で比較する診断用スイッチです。モデル全体の出力や token 列を比較するものではなく、比較対象の kernel が実行された場合だけ働きます。通常の生成を高速化する設定ではありません。

`strata` は GGUF の model family が Qwen3.6 (`qwen35moe`) なら、この専用 engine に処理を渡します。engine は `Engine` の構築時に環境変数の有無を読み、`verify_k` に保持します。

## 値と判定

値の内容は parse せず、`std::getenv(...) != nullptr` だけで判定します。

| 状態 | 動作 |
|---|---|
| 未設定 | 検証を無効化 |
| 任意の値を設定 | 検証を有効化。`1` 以外や空文字も有効 |

engine の構築時に一度評価され、その engine の実行中は保存された値を使います。構築後に環境を書き換えても、この判定は変わりません。

## 有効になる条件

- Qwen3.6 専用 engine がビルドに含まれ、Qwen3.6-35B-A3B のモデルが選択されていること。
- 比較する独自 kernel の分岐が実際に選ばれること。たとえば `q8_small` は `fast_k` が有効で、重み型が Q8_0、列数が 1〜8、入力幅が32の倍数などの条件を満たすときだけ対象です。router/grouping、add+RMS、shared expert、MoE 出力にもそれぞれ形状や経路の条件があります。
- `STRATA_Q36_OLD_KERNELS` が設定されていると `fast_k` が無効になり、新 kernel が選ばれないため、この変数を設定していても多くの比較箇所は通りません。

既存の `docs/QWEN36.md` は `STRATA_Q36_VERIFY=1` と `--no-graph` を組み合わせた実行例を示しています。コード上、比較関数は CUDA stream を同期し、device 結果を host にコピーして比較します。検証時はこの例のように graph を無効にします。

## 実行時の詳細

検証対象の処理では、新 kernel の結果を scratch buffer に残し、従来 kernel も同じ入力から実行して比較します。`verify_cmp` は stream を同期して両方の結果を host にコピーし、float 配列は各要素の全ビットを `memcmp` で比較します。router の grouping は整数の group 数、pointer、start、destination、token 配列を比較します。

不一致があると stderr に `strata-q36 VERIFY MISMATCH ...` を出します。通常の float 比較は比較種別ごとに最初の3件まで詳細を表示します。grouping の不一致は累計20件まで概要を表示します。engine 終了時には stderr に比較総数・不一致総数と、比較種別ごとの不一致数を出します。環境変数を設定しただけで比較対象が実行されなければ、集計は0件になり得ます。

関連する `STRATA_Q36_VDEBUG` が設定されていると、q8 比較で不一致が出た場合に限って、対象 block の診断も追加出力します。これは `STRATA_Q36_VERIFY` の有効条件ではありません。

## 根拠

- `src/program/generate.cpp:2252-2265` — Qwen3.6 model family を専用 engine に渡す分岐。
- `src/qwen35/q36_engine.cu:1575-1580` — `STRATA_Q36_VERIFY` の有無による判定、旧 kernel との切替状態、集計値。
- `src/qwen35/q36_engine.cu:1581-1594,1614-1624,1631-1638` — stream 同期、host コピー、bitwise 比較、不一致ログ、q8 検証と VDEBUG 条件。
- `src/qwen35/q36_engine.cu:1672-1690,1695-1731,1752-1787,1792-1812,1836-1861` — add+RMS、shared expert、grouping/router、MoE 出力の比較経路と適用条件。
- `src/qwen35/q36_engine.cu:2000-2005` — 検証中は fused router-ext 経路を選ばない条件。
- `src/qwen35/q36_engine.cu:3865-3871` — engine 終了時の集計ログ。
- `docs/QWEN36.md:130-134` — `--no-graph` での使用例と、同資料で報告された比較数・不一致数。これらは同資料の記録であり、本調査で再計測した値ではありません。
