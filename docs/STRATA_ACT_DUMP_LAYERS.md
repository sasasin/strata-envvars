# `STRATA_ACT_DUMP_LAYERS`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの動作は対象外。

## 役割

CPU native expert の activation second moment dump で対象にする layer 番号を指定します。指定 layer の gate/up 入力と down 入力について、各チャネルの二乗和を蓄積し、必要なら full covariance もファイルに書きます。これは研究・解析用のフックです。

この変数だけでは dump は始まりません。`STRATA_ACT_DUMP` に空でない出力 prefix が必要です。また、実際に記録されるのは `native_quant_act()` / `native_quant_h()` が呼ばれた入力だけです。通常の CPU expert 経路では、対象 layer に CPU 側の仕事があると gate/up activation が量子化されるときに記録し、down activation は CPU expert の計算へ渡すときに記録します。Q2 native kernel が独自の `act_quant_any()` を使う経路では、この記録関数を通らない場合があります。

## 値と判定

実装は文字列全体を数値として検証せず、カンマで区切った各要素の先頭を `std::atoi()` に渡します。読み取った整数を layer 番号の配列に加え、配列が空でなければ dump を有効にします。

| 値 | 扱い |
|---|---|
| unset / 空文字 | layer 配列が空になり、dump 無効 |
| `10,20` | layer 10 と 20 を対象にする |
| `  +10tail,20xyz` | `atoi()` の変換結果である 10 と 20 を対象にする。文字列全体の妥当性は検査しない |
| `abc` | `atoi()` が 0 を返すため、layer 0 を対象にして dump は有効 |
| `10,` | 10 のみ。末尾カンマの後ろに空要素は追加されない |
| `,10` / `10,,20` | 空要素も `atoi()` で 0 になり、layer 0 が追加される |

大文字小文字の比較はありません。重複した番号はそのまま配列に入りますが、記録時は layer の存在を検索するだけなので、同じ入力が重複記録されることはありません。layer 番号の範囲検査もありません。通常の layer 番号は 0 始まりなので、実在しない番号は記録対象と一致しません。

根拠: `src/kernels/cpu/native_expert.cpp:152-169,191-194`。

## 有効になる条件

- `STRATA_ACT_DUMP` が設定され、かつ先頭文字が NUL ではないこと。未設定または空文字なら constructor が早期 return し、この変数も読みません。
- `STRATA_ACT_DUMP_LAYERS` が空でないこと。値の変換結果が実在 layer と一致しなくても `on` 自体は true になります。
- 対象 layer で `native_quant_act()` または `native_quant_h()` が呼ばれること。どちらの関数も選択 layer 以外を `act_dump_record()` 内で除外します。
- この実装は `STRATA_NATIVE_EXPERTS` 有効時にビルドされる native expert コードです。CMake では同オプションは既定 ON ですが、無効ビルドでは native pack を拒否し、実装関数は abort stub になります。

関連する `STRATA_ACT_DUMP_COV` は、設定値を `atoi()` し 0 以外なら共分散を追加します。単に変数が設定されているだけでは有効にならず、空文字や非数値文字列は 0 扱いです。

## 実行時の詳細

設定は `ActDump` の初回生成時に一度読み取られます。生成は `act_dump()` の初回呼び出し時に遅延され、生成後にプロセス環境を変更しても再読込されません。layer 番号は `expert_layout_load()` が各 layer の `NativeFmt.layer` に 0 から順に設定します。

gate/up 用の `gu` 記録は、Hadamard-folded layer なら回転後、activation を量子化する直前のベクトルを使います。down 用の `dn` 記録も同様に `native_quant_h()` の Hadamard 回転後・量子化前です。各記録について `sum(x[i] * x[i])` と count を加算し、共分散モードでは `sum(x[i] * x[j])` も蓄積します。

出力は `<prefix>_L<layer>_gu.bin` と `<prefix>_L<layer>_dn.bin` です。ファイルはホスト表現の int64 `n`、int64 `count`、double の `sum x^2[n]`、共分散モード時は続けて double の `sum x x^T[n*n]` を順に書いたバイナリです。記録回数は全 layer・両 kind を通した合計で数え、共分散なしでは 2000 records ごと、共分散ありでは 400000 records ごとに flush し、終了時にも flush します。ソースコメントの「every 2000 records」は共分散ありの実装 cadence と異なるため、上記は実際の分岐条件に基づきます。

flush は `<出力ファイル>.tmp` を開いて書き、成功時に元の名前へ rename します。`fopen()` が失敗するとそのファイルの書き込みを黙って skip し、ディレクトリ作成やエラーログは行いません。データが一度も記録されなかった layer/kind のファイルも作られません。

## 根拠

- 読み取り、layer list の parse、dump 有効化、終了時 flush 登録: `src/kernels/cpu/native_expert.cpp:152-169`。
- 集計、出力形式、flush の頻度と一時ファイル rename: `src/kernels/cpu/native_expert.cpp:176-213`。
- gate/up と down の記録位置（Hadamard 回転後、量子化前）: `src/kernels/cpu/native_expert.cpp:217-240`。
- `NativeFmt.layer` の 0 始まり設定: `src/kernels/cpu/expert_layout.cpp:506`。
- decode で CPU 側 expert がある場合の native activation 量子化呼び出し: `src/core/expert_source.cpp:5004-5016`。
- prompt path で CPU expert が使う token の gate/up activation を量子化する呼び出し: `src/prefill/prefill.cpp:4016-4033`。
- ビルド既定値と native expert ソースの条件付き追加: `CMakeLists.txt:128,1712-1761`。
- dump を読む同梱ツールは先頭 16 byte を int64 の `n` と count、その後を double 配列として解釈: `tools/trellis/merge_dumps.py:1-30`。
- `docs/DETAILS.md` にはこの変数または activation dump の測定値・個別説明は見つからなかった。
