# `strata-hy4 --trace-mut`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root、CUDA/HIP） |
| オプション | `--trace-mut` |
| 別名 | なし |
| 値 | `atoi` で整数に変換する値。0 以上のとき差し替えを有効化する。 |

## 役割

`--trace-m` が有効な比較ダンプ実行で、比較対象窓の末尾位置にある入力 token ID を指定値へ置き換える。後続 token の計算が変更前と同じかを調べる因果性確認に使う。これは通常の生成入力を変更するためのオプションではなく、トレース分岐だけで作用する。

## 使い方

```sh
# prompt.ids の末尾 token を ID 1234 に置き換え、4 token 窓の中間値を比較用に出力する。
strata-hy4 --model model.strata --tokens prompt.ids --trace-m 4 --trace-mut 1234 --out trace-out
```

このコマンド例はオフライン実行用で、`1234` は対象モデルで有効な token ID に置き換える。ソースでは ID のモデル語彙範囲検証をしていない。

## 値と既定値

- 値は必須。引数がない場合、共通の値取得処理が `ERR --trace-mut needs a value` を標準出力へ出し、終了コード 2 で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`）。
- 省略時の内部値は `-1`。差し替えは行わない。指定値は `atoi` で読むため、整数としての厳密な書式・範囲検証はない。変換結果が負なら無効、0 以上なら有効（同 `:373`, `:438`, `:798`）。
- `--trace-mut` 単独ではトレース分岐に入らず、通常経路の token は変更しない。`--trace-m` の値が 1 以上のときに限り、差し替え処理が実行される（同 `:793-798`）。
- 同じオプションを複数回指定した場合、引数解析ループで後に現れた値が変数へ再代入される（同 `:375-384`, `:438`）。

## 実行時の動作

コマンドライン解析後、モデル・token 入力のロード、Runner 初期化、prompt の prefill が行われる。`--trace-m > 0` の分岐では窓の開始位置を `p0 = T0 - M - trace_off` とし、`--trace-mut` が 0 以上なら `tok[T0 - 1 - trace_off]` を指定値に差し替える。この添字は窓の最後の token に対応する。変更後の同一 token 配列を使い、窓内の各位置を1 tokenずつ処理して `seq0` から `seq<M-1>` へ、続いて窓全体を一括処理して `win` へ中間値をダンプし、成功時は `[trace] M=... window p0=... dumped` を標準出力へ出して終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:632-638`, `:748-789`, `:793-817`）。

この差し替えは prefill 完了後に行われるため、既に完了した prefill を再計算しない一方、比較用の逐次・窓一括 forward の双方には変更後の token 配列が使われる。`--trace-mut` はトレース経路より前に `--serve` の処理が分岐・復帰するサーバーモードでは適用されない（同 `:397`, `:575-612`, `:793-798`）。

## 適用条件と副作用

- `--trace-m` が 1 以上であることが必要。0 以下なら token は変更されず、通常処理が続く（`engine/src/hy4flash/run/hy4_main.hip.cpp:793-798`）。
- 置換値が 0 以上かどうかだけを確認し、モデル語彙内の token ID かは検証しない。`--trace-off` による添字の妥当性や `--trace-m` が入力長に収まるかも、このトレース箇所では検証されない。入力長・値の組み合わせによっては有効な prompt 窓にならないため、入力 token 数と窓・offset を合わせること（同 `:436-439`, `:793-807`）。
- ダンプは `--out` の下に `seq0...seq<M-1>` と `win` のディレクトリを作成し、各 forward の中間値を `.npy` に保存する。出力先が既存なら同名ファイルを `fopen(..., "wb")` で開くため上書きされる。書き込み先を選び、必要な既存データを退避すること（同 `:801-814`; `engine/src/hy4flash/run/hy4_graph.hip.h:77-96`, `:1934-1942`）。
- `--dump-layer` を併用した場合は指定 layer の attention 内部 buffer も同じ dump directory に出力する。未指定時の `dump_layer` は `-1` で、特定 layer の内部 dump 条件には一致しない（`engine/src/hy4flash/run/hy4_main.hip.cpp:373`, `:439`, `:801-802`; `engine/src/hy4flash/run/hy4_graph.hip.h:207-217`, `:2170-2182`）。
- トレース分岐は標準の生成・decode 経路に続行せず、ダンプ後に return する（`engine/src/hy4flash/run/hy4_main.hip.cpp:793-817`）。

## 出力とエラー

- 引数値が欠けている場合は標準出力に `ERR --trace-mut needs a value`、終了コード 2（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`）。
- 未知の引数は標準エラーに `unknown arg ...` を出して終了コード 2（同 `:498-505`）。
- トレース forward が失敗すると終了コード 1 で戻るが、この分岐は `err` の内容を表示しない（同 `:807-814`）。成功時は標準出力に `[trace] ... dumped` を出す（同 `:815-817`）。
- `.npy` 保存 helper は出力ファイルを開けない場合にその場で戻り、呼び出し元へ失敗を通知しない。このため、成功メッセージだけでは全 dump ファイルの作成成功を確認できない（`engine/src/hy4flash/run/hy4_graph.hip.h:77-96`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:373` — `trace_mut` の初期値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`, `:436-439` — 必須値処理と `atoi` による parser 登録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:632-638`, `:748-789` — token 入力と prefill の順序。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:793-817` — trace 条件、置換添字、逐次・窓 forward、出力先、完了表示と終了。
- `engine/src/hy4flash/run/hy4_graph.hip.h:77-96`, `:1934-1942`, `:2170-2182` — `.npy` 書き込み、dump の保存、layer 内部 buffer の追加出力。
- `docs/cli/README.md:1277-1283`, `:1351-1355` — `strata-hy4` のツール・コマンド階層および `--trace-mut` の索引リンク。動作説明の根拠ではなく、対象スコープとの照合に使用。

