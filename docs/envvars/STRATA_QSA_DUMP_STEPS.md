# `STRATA_QSA_DUMP_STEPS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA/HIP の prompt prefill で、QSA の選択記録に各 query の `steps` 配列を追加します。これは環境変数の値に基づいて処理を切り替える診断用フックです。通常の QSA 計算や結果を有効化するスイッチではありません。実際の記録には別途 `STRATA_QSA_DUMP` にファイル名を設定する必要があります。

## 値と判定

値は parse されません。記録処理の該当箇所で `std::getenv("STRATA_QSA_DUMP_STEPS")` が null でないかだけを判定します。

| 状態 | 挙動 |
|---|---|
| 未設定 | 選択セルの配列までを書き、`steps` 配列を追加しない |
| 設定あり（空文字を含む） | `steps` 配列も追加する |

`1`、`0`、その他の文字列の区別、大文字小文字、数値変換、範囲制限はありません。設定値が空でも有効です。

## 有効になる条件

`STRATA_QSA_DUMP_STEPS` だけでは出力されません。次の条件も必要です。

- QSA の処理が実行される prompt prefill 経路である。
- `STRATA_QSA_DUMP` が設定されている。値はファイルパスとして使われ、空文字なら空のパスで開こうとするため、通常はファイルを開けません。
- 現在の chunk が記録対象の末尾位置に重なる。境界は `p0 + T > pos0 + n - last` で判定され、`last` は `STRATA_QSA_DUMP_LAST` が未設定なら 4096、設定時は `atoll` の結果です。
- `STRATA_QSA_DUMP_LAYER` が未設定、またはその `atoi` の結果が現在の QSA layer index と一致する。未設定時の既定値は `-1`（全 QSA layer）。

このコードは `src/prefill/prefill.cpp` にあり、同ファイルは `strata_prefill` ターゲットに含まれます。CMake の当該ターゲットは CUDA/HIP runtime とリンクされます。SYCL 側の `sycl/src/prefill/prefill.cpp` には `STRATA_QSA_DUMP` と `STRATA_QSA_DUMP_LAST` の別実装がありますが、`STRATA_QSA_DUMP_STEPS` の読み取りは確認できません。

## 実行時の詳細

対象 chunk/layer では GPU 上の `m.sel_ids` をホストにコピーして stream を同期し、`STRATA_QSA_DUMP` のパスを append binary mode (`"ab"`) で開きます。ファイルには順に、4 個の `int32` ヘッダー `{qsa layer, p0, T, cap}`、`T * cap` 個の選択 cell (`int32`)、そしてこの変数が設定済みなら `T * kStepCount` 個の `int32` steps が書かれます。したがって、この変数を設定しない記録は steps を必要とする `tests/cuda/pa_bench.cpp` の入力形式を満たしません。

`STRATA_QSA_DUMP_STEPS` は各該当記録で直接 `getenv` され、関数内の `static` キャッシュには入りません。プロセス内で環境を書き換える場合、後続記録の判定に反映されます。`STRATA_QSA_DUMP_LAST` と `STRATA_QSA_DUMP_LAYER` は `static` ローカル初期化で一度だけ読み込まれます。ファイルを開けない場合は記録をスキップし、この箇所からは警告・エラーを出しません。`fwrite` の戻り値も確認していません。

## 根拠

- `src/prefill/prefill.cpp:3231-3254` — dump の条件、既定値、層フィルター、ヘッダー・selection・steps の出力、append mode。
- `CMakeLists.txt:679-685` — `src/prefill/prefill.cpp` を含む `strata_prefill` ターゲットと GPU runtime のリンク。
- `sycl/src/prefill/prefill.cpp:3129-3134` — SYCL 側の QSA dump 実装。ここでは `STRATA_QSA_DUMP_STEPS` を読み取らない。
- `tests/cuda/pa_bench.cpp:1-3,27-34` — steps 付き dump の形式を利用するベンチマーク側の説明と、steps 不足時のエラー。ただしベンチマークは変数の本番動作根拠には用いていない。
