# `STRATA_SPEC_ADAPT_WARM`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

投機デコード（`--spec >= 2`）開始後、指定した数の verify round だけ適応型 expert tier の入れ替え間隔を短くするための値です。最初の `STRATA_SPEC_ADAPT_WARM` round 中は `STRATA_SPEC_ADAPT_EVERY` ごとに適応し、その期間が終わると通常の `--adapt-every` 間隔に戻ります。適応 tier が使う routing usage が空なら、設定にかかわらず適応処理は走りません。

## 値と判定

`--adapt-every` が CLI で明示されていない場合に限り、`--spec >= 2` かつ通常の `adapt_every > 0` のとき両環境変数を読みます。値は `atoi` / `atoll` で変換されるため、文字列全体の厳密な数値検証ではありません。

| 条件 | 結果 |
|---|---|
| `STRATA_SPEC_ADAPT_EVERY` が未設定または `atoi` 結果が 0 以下 | warm-up 間隔を設定しない |
| `STRATA_SPEC_ADAPT_EVERY` の `atoi` 結果が通常の `--adapt-every` 以上 | warm-up 間隔を設定しない |
| `STRATA_SPEC_ADAPT_WARM` が未設定または `atoll` 結果が 0 以下 | warm-up 期間を設定しない |
| 上記を満たし、両方の値が正で warm-up 間隔が通常間隔より小さい | warm-up 期間中だけ短い間隔を使う |

例えば `2junk` は `atoi` で 2、`200rounds` は `atoll` で 200 として扱われます。空文字や数値に変換できない文字列は 0 になり、負数も採用されません。間隔値が通常間隔以上の場合は warm-up 全体が適用されません。

## 有効になる条件

- `--adapt-every N` をコマンドラインで指定すると、この環境変数による上書きは行いません。明示された値が 0 の場合も同じです。
- `--spec` が 2 以上で、通常の `adapt_every` が正である必要があります。
- 適応型 tier の usage が空でない場合にのみ、計算された間隔で適応処理が起動します。
- CUDA 起動時の既定値注入は、全可視 GPU の compute capability が同一である場合に行われます。そのうち `STRATA_SPEC_ADAPT_SM86=1` の先頭文字判定を満たす sm_86 では、`STRATA_SM86_PERF` が先頭文字 `0` でなく、対象の二変数が未設定なら `STRATA_SPEC_ADAPT_EVERY=2` と `STRATA_SPEC_ADAPT_WARM=200` がプロセス環境へ設定されます。ユーザーが空文字を含め何か設定していれば、その値は既定値に置き換えられません。
- 上記の sm_86 既定値注入は `STRATA_USE_HIP` および `STRATA_GPU_METAL` が定義されるビルドでは呼び出されません。環境変数を直接読む warm-up 処理が実際に組み込まれる対象ビルドについては、該当する `src/program/generate.cpp` の経路に限ります。

## 実行時の詳細

sm_86 の既定値処理は GPU 属性を確認した起動時に実行され、`STRATA_SPEC_ADAPT_SM86` が先頭文字 `1` でなければ何もしません。続いて `generate.cpp` がオプション初期化中に warm-up 値を読み、`adapt_warm_every` と `adapt_warm_rounds` に保存します。この読み取り後に環境を変更しても実行中の値には反映されません。warm-up の期限判定は `rounds < adapt_warm_rounds` です。期限後は `adapt_every` が使われ、各 generation 経路の verify round ごとにこの間隔で適応処理を起動するか決めます。

この変数専用のログ出力はありません。sm_86 の既定値注入も、これら二変数を設定したことを示すログを出しません。

## 根拠

- `src/program/generate.cpp:690-694` — 通常間隔と warm-up 間隔、round に応じた間隔選択。
- `src/program/generate.cpp:2626` — `--adapt-every` の値と明示指定フラグ。
- `src/program/generate.cpp:3220-3229` — 条件、環境変数の変換、warm-up 値の採用条件。
- `src/program/generate.cpp:2840-2853` — CUDA デバイス確認後に既定値を適用する呼び出し。
- `src/core/nv_defaults.cpp:12-15,73-91` — `STRATA_SM86_PERF` の先頭文字判定、sm_86 と `STRATA_SPEC_ADAPT_SM86` の opt-in 条件、ユーザー設定を保った既定値注入。
- `src/program/generate.cpp:14449-14452,15119-15123,16662-16668` — 適応 tier が空でない場合の間隔判定と起動箇所。
- `include/strata/core/nv_defaults.hpp:34-38` — この既定値の適用範囲についての実装注記。`docs/DETAILS.md` にこの warm-up 値の測定条件を記載した説明は見つからなかったため、性能効果は記載していません。
