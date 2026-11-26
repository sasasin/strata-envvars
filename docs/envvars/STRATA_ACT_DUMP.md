# `STRATA_ACT_DUMP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査開始時の checkout は `## main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

## 役割

CPU native expert の活性化を集計し、指定 prefix を付けたバイナリファイルへ書き出す研究・較正用の環境変数です。変数値自体は有効化フラグではなくファイル名の prefix です。ダンプを有効にするには、この変数に空でない prefix を設定し、さらに `STRATA_ACT_DUMP_LAYERS` で少なくとも一つの layer を指定します。収集対象は CPU native expert の gate/up 入力と down 入力であり、GPU で処理される expert の入力をこのコードが記録するものではありません（`engine/src/kernels/cpu/native_expert.cpp:432-436,449-465,488-505`、`engine/src/core/expert_source.cpp:5747-5757,5878-5892`）。

各 layer・入力種別について、ベクトル要素ごとの二乗和 `sum(x[i]^2)` と記録数を累積します。gate/up 側は token ごとの入力、down 側は CPU routed expert の SwiGLU 出力です。層の expert が Hadamard-folded なら、量子化前に回転したベクトルを記録します。したがって記録値は回転後の CPU expert 用 basis であり、平均二乗や中心化共分散をその場で出力するものではありません（`engine/src/kernels/cpu/native_expert.cpp:432-436,514-537`）。

この機能は CPU native expert の `native_quant_act` / `native_quant_h` に置かれています。通常の生成結果や expert の選択を変更せず、同じ関数内で記録した後に従来の活性化量子化を続けます（`engine/src/kernels/cpu/native_expert.cpp:514-537`）。

候補名の全参照を検索した結果、実際に `STRATA_ACT_DUMP` の値を `getenv` で読むのは上記 `ActDump` constructor だけでした。設定登録 JSON の名前はメタデータであり、Trellis の `build_swap.py` / `merge_dumps.py` などは生成済み dump ファイルを読む側です。`run_parts.py` は `--dump-dir` 指定時に `STRATA_ACT_DUMP=<prefix>` を runner 引数へ追加して渡しますが、そこで値を解析・読み取りはしません（`terminal/data/settings-register.json:27-56`、`terminal/tools/trellis/run_parts.py:58-65`、`terminal/tools/trellis/build_swap.py:56-74`、`terminal/tools/trellis/merge_dumps.py:11-31`）。

## 値と判定

`STRATA_ACT_DUMP` は `std::getenv` で読み、未設定または空文字列なら constructor がそこで終了します。空でない文字列はそのまま prefix に使い、真偽値や数値として parse しません。空白除去、パス検証、ディレクトリ作成、値の範囲検査もありません（`engine/src/kernels/cpu/native_expert.cpp:449-453`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| すべての build | `STRATA_ACT_DUMP` が unset または `""` なら prefix がなく無効 | 空でない任意の文字列（例: `act`、`/tmp/cal/act`、`0`、`true`）。ただし layer 指定も必要 | 値だけで無効となる非空文字列はない。相対/絶対パスの妥当性は検査されない |

実際の記録可否は `STRATA_ACT_DUMP_LAYERS` にも依存します。未設定または空文字列では layer リストが空なので機能は無効です。値はカンマ区切りで走査され、各要素を `std::atoi` で整数化します。全体の妥当性検査や空白 trim はせず、数値の後ろの文字は `atoi` が変換できる先頭部分までしか影響しません。例えば `2,4` は layer 2 と 4、`2junk` は 2、`abc` は 0 を指定します。`2,,4` の空要素も `atoi("")` により 0 になり、負数など範囲外の値もリストには入りますが、実在 layer と一致しなければ記録されません（`engine/src/kernels/cpu/native_expert.cpp:454-464,488-490`）。

`STRATA_ACT_DUMP_COV` は prefix が空でない場合に読み取られ、設定されていて `std::atoi(value) != 0` のときだけ共分散行列も累積します。よって unset・空文字・`0`・`0anything`・`true` は無効、`1`・`-1`・`2tail` は有効です。数値としての全体妥当性、大文字小文字、空白の検査はありません（`engine/src/kernels/cpu/native_expert.cpp:451-454,496-504`）。

## 有効になる条件

- 出力 prefix が空でなく、`STRATA_ACT_DUMP_LAYERS` が空でないこと。prefix だけ、あるいは layer 指定だけでは記録しません（`engine/src/kernels/cpu/native_expert.cpp:449-465`）。
- `STRATA_NATIVE_EXPERTS` を有効にしたビルドであること。CMake の option は既定 `ON` ですが、無効 build には native expert 実装がなく、native expert pack の読み込みは `this pack has native (IQ) experts but the engine was built without STRATA_NATIVE_EXPERTS` で拒否されます（`engine/CMakeLists.txt:178`、`engine/cmake/backends/cpu.cmake:370`、`engine/src/kernels/cpu/expert_layout.cpp:488-515`）。
- 実行経路で対象 layer の CPU native expert 活性化量子化関数が呼ばれること。通常 pack は `act_quant_q8_1` を通り、native pack でも Q2_0 用の分岐は `act_quant_any` を使うため、このダンプ関数を通りません（`engine/src/core/expert_source.cpp:5747-5757`、`engine/src/kernels/cpu/pool.cpp:1589-1594`）。GPU 側で処理されるだけの token/expert の入力も CPU 関数では記録されません（`engine/src/core/expert_source.cpp:5747-5757,5827-5837`）。
- 指定 layer が `expert_layout_load` で割り当てられた layer と一致すること。値は layer 範囲を検査せず、合致しなければその layer の記録は発生しません（`engine/src/kernels/cpu/expert_layout.cpp:501-520,619-620`、`engine/src/kernels/cpu/native_expert.cpp:488-490`）。

ほかの Strata CLI 引数や設定ファイルが prefix を上書きする処理は見つかりませんでした。`--pack` の native expert 配置と、実行時に CPU に割り当てられた expert の処理経路が前提であり、OS や GPU backend による値の再解釈はコードにありません（`engine/src/program/generate.cpp:5378-5391`、`engine/src/core/expert_source.cpp:5747-5757`）。

## 実行時の詳細

`ActDump` は `act_dump()` 内の関数ローカル static ポインタから初回アクセス時に一度だけ生成されます。最初の `native_quant_act` または `native_quant_h` で環境を読み、以後の呼び出しは prefix・layer・共分散設定をキャッシュした同じ状態を使います。プロセス実行中に環境値を変えても反映されません。prefix が未設定/空なら constructor は layer や共分散の環境変数を読まずに終了します（`engine/src/kernels/cpu/native_expert.cpp:449-471,514-537`）。

有効時、`native_quant_act` は Hadamard 回転を適用した後、`native_quant_h` も同様に回転した後で、それぞれのベクトルを記録し、その後に通常の量子化を行います。gate/up 入力は CPU expert を含む token の CPU activation quantize 経路で作られ、down 入力は CPU expert job ごとの SwiGLU 結果を量子化する際に作られます。`act_dump_record` は指定 layer のみを記録し、二乗和・任意の外積和・件数を mutex 下で更新します（`engine/src/core/expert_source.cpp:5747-5757,5878-5892`、`engine/src/kernels/cpu/pool.cpp:1438-1453,1589-1594`、`engine/src/kernels/cpu/native_expert.cpp:488-505,514-537`）。

出力名は `<prefix>_L<layer>_gu.bin` と `<prefix>_L<layer>_dn.bin` です。ファイル内容は順に 8 byte の `int64 n`、8 byte の `int64 count`、`n` 個の 8 byte `double` 二乗和、そして共分散有効時だけ `n*n` 個の 8 byte `double` 外積和です。値は C++ の `fwrite` でそのホストの表現のまま書かれます（`engine/src/kernels/cpu/native_expert.cpp:473-486,492-505`）。

出力は `.tmp` に書いてから最終名へ `rename` します。累積 record 数が共分散なしなら 2000 件ごと、共分散ありなら 400000 件ごとに flush し、さらに有効化時に登録した `atexit` handler から終了時にも flush します。コードコメントには一律「every 2000 records」とありますが、実際の条件式は共分散ありで 400000 件です（`engine/src/kernels/cpu/native_expert.cpp:432-436,465,473-486,506-509`）。データが一件もない layer/kind のファイルは作られません（`engine/src/kernels/cpu/native_expert.cpp:473-486,492-505`）。

## ログと測定値

この収集処理自身は有効・無効のログを出しません。`.tmp` の `fopen` が失敗した場合はその出力を飛ばして続行し、`fwrite` と `rename` の戻り値も検査しないため、書き込み失敗をこの処理がログや終了コードで通知する経路はありません（`engine/src/kernels/cpu/native_expert.cpp:473-486`）。親ディレクトリも作成しません。

Strata の `docs/DETAILS.md` にこの環境変数の説明や測定値は見つかりませんでした。コードコメントと実装に測定条件付きの性能値はなく、ここでは性能・精度の測定値を記載しません。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:432-537` — dump 状態、環境変数の parse、記録/flush、2 種の入力の記録位置。
- `engine/src/kernels/cpu/expert_layout.cpp:488-520,619-620` — `STRATA_NATIVE_EXPERTS` のない build と layer の形式設定。
- `engine/src/core/expert_source.cpp:5747-5757,5827-5837,5878-5892` — CPU/GPU 経路の分岐と native CPU expert job の実行。
- `engine/src/kernels/cpu/pool.cpp:1438-1453,1589-1594` — gate/up 出力後の down 入力量子化と Q2_0 分岐。
- `engine/CMakeLists.txt:178`、`engine/cmake/backends/cpu.cmake:370` — native expert build option と compile definition。

