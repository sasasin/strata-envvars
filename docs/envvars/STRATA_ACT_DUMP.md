# `STRATA_ACT_DUMP`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

CPU native expert 用に量子化する前の活性ベクトルから、成分ごとの二次モーメント `sum(x[i]^2)` を集計してファイルに書きます。ゲート・アップ入力（token の hidden state）を `_gu.bin`、down 入力（CPU が計算する routed expert の SwiGLU 出力）を `_dn.bin` に記録します。Hadamard-folded 層では、各入力をその層の回転後の基底で記録します。

これは研究・キャリブレーション用の計測フックです。通常の推論設定を変えるものではなく、記録が有効でも CPU native expert の量子化・計算は続行します。ビルドで `STRATA_NATIVE_EXPERTS` が有効なときにコンパイルされる `src/kernels/cpu/native_expert.cpp` に実装されています。

## 値と判定

| 変数 | 判定 |
|---|---|
| `STRATA_ACT_DUMP` | unset または空文字なら無効。空でない値全体をファイル名 prefix として使う。数値や真偽値としては parse しない。 |
| `STRATA_ACT_DUMP_LAYERS` | カンマ区切りで `atoi` に渡した整数を層番号として選ぶ。unset または空文字なら層リストが空になり、記録は無効。`atoi` のため、先頭の整数部分だけが使われ、整数で始まらない要素は `0` になる（例: `10x` は 10、`abc` は 0）。大文字小文字の規則は関係しない。 |
| `STRATA_ACT_DUMP_COV` | prefix が有効な場合に読み取る。unset、空文字、`atoi` の結果が 0 なら共分散なし。整数変換結果が 0 以外なら共分散を追加する。たとえば `1`, `-1`, `2x` は有効、`0`, `false`, 空文字は無効。 |

層番号の空白や符号は `atoi` の規則に従います。実在する `NativeFmt::layer` と一致しない番号は記録されません。層番号は native expert layout の読み込み時に `0` から設定されます。

## 有効になる条件

- `STRATA_ACT_DUMP` に空でない prefix があり、`STRATA_ACT_DUMP_LAYERS` から少なくとも1要素が parse される必要があります。prefix だけ設定しても記録は始まりません。
- 該当層の CPU native expert 経路が `native_quant_act()` または `native_quant_h()` を呼ぶ必要があります。通常の decode では CPU が native expert を計算する場合が対象です。Q2 native kernels を使う層はこれらの関数を通らず、対象になりません。prefill でも CPU native expert の活性を量子化する経路で呼ばれます。
- `native_quant_act()` / `native_quant_h()` を呼ぶ計測・テスト経路もサンプルを加えます。したがって、設定したプロセスでそれらの関数に合成入力を渡す処理が実行されれば、その入力も集計対象です。
- `STRATA_ACT_DUMP_COV` は prefix が空でないときだけ読み取られます。共分散は入力幅 `n` ごとに `n*n` 個の `double` を保持するため、選択層・記録種別ごとのメモリ量が大きくなります。

## 実行時の詳細

環境変数は `ActDump` の初回生成時に読み取られ、プロセス内の static インスタンスに保存されます。生成は `native_quant_act()` / `native_quant_h()` から `act_dump()` が初めて呼ばれたときです。以降にプロセス環境を変更しても、prefix・層・共分散設定は再評価されません。

記録対象のベクトルごとに、各成分の二乗を `double` に加算し、`count` を1増やします。共分散を有効にした場合は、加えて行優先で `sum(x[i] * x[j])` を蓄積します。サンプルごとの記録は mutex で保護されます。記録数はプロセス全体で数えられ、共分散なしでは2,000件ごと、共分散ありでは400,000件ごとに flush を試み、正常終了時にも `atexit` から flush します。

出力名は `<prefix>_L<layer>_gu.bin` と `<prefix>_L<layer>_dn.bin` です。各ファイルはバイナリで、先頭に `int64 n`、続いて `int64 count`、`n` 個の `double sum(x[i]^2)`、共分散有効時はさらに `n*n` 個の `double sum(x[i]*x[j])` を書きます。flush は `<path>.tmp` を `wb` で開いて書いた後、最終名へ rename します。親ディレクトリは作成しません。ファイルを開けない場合はそのファイルを黙って skip し、書き込み・rename の失敗もログに出しません。

`tools/trellis/run_parts.py` は `--dump-dir` が指定されたとき、runner に `STRATA_ACT_DUMP=<part-dir>/act` を渡します。層選択や共分散はこのスクリプトでは追加設定しません。

## 根拠

- `CMakeLists.txt:128,1656-1761` — `STRATA_NATIVE_EXPERTS` のビルドオプションと native expert 実装の追加。
- `src/kernels/cpu/native_expert.cpp:135-168` — 変数の読み取り、既定値、層 parse、遅延初期化と終了時 flush 登録。
- `src/kernels/cpu/native_expert.cpp:176-213` — ファイル形式、flush、二次モーメント・共分散の集計と flush 間隔。
- `src/kernels/cpu/native_expert.cpp:217-240` — Hadamard 回転後の gate/up・down 入力を記録し、その後に量子化する処理。
- `src/kernels/cpu/expert_layout.cpp:506-516` — native layout の層番号と Hadamard 層設定。
- `src/core/expert_source.cpp:5005-5016` — decode で CPU 計算対象がある場合の活性量子化。Q2 経路は `native_quant_act()` を迂回する。
- `src/kernels/cpu/pool.cpp:1359-1380` — CPU native expert の SwiGLU 出力を down 入力として量子化する経路。
- `src/prefill/prefill.cpp:4016-4048` — prefill の CPU native expert で gate/up 活性を量子化する経路。
- `tools/trellis/run_parts.py:58-65` — trellis の分割 runner から prefix を渡す処理。

`docs/DETAILS.md` にこの変数の記述は見つかりませんでした。性能・正確性の測定値は確認できる資料がないため記載していません。
