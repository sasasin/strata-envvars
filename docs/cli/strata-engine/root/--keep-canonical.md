# `--keep-canonical`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` エンジン引数（`strata generate`） |
| オプション | `--keep-canonical` |
| 別名 | なし |
| 値 | なし（真偽フラグ） |

## 役割

ネイティブ形式で提供されるテンソルについても、pack 内の canonical copy をロードする A/B 用フラグです。通常は native 経路が担当する canonical copy を省き、その分を VRAM の節約に回します。フラグを指定すると native 側の重みと canonical copy の両方が保持され、使用 VRAM が増えます（`src/program/generate.cpp:602, 889, 3774-3777`）。

## 使い方

```sh
strata generate --pack /path/to/pack --tokens '1,2,3' \
  --native /path/to/model-00001-of-00002.gguf --keep-canonical
```

`--native` はネイティブモデル経路の例です。通常の pack で canonical copy を省略する条件は、対応する native GGUF を指定してネイティブ供給対象があることです。例のパスは形式を示すもので、実在するモデル構成を保証しません（`src/program/generate.cpp:808-817, 3232-3272`）。

## 値と既定値

値を取らないフラグです。parser は `--keep-canonical` を見つけると `true` に設定し、既定値は `false` です。同じ指定を複数回しても同じ真偽値のままです（`src/program/generate.cpp:602, 2780`）。

## 実行時の動作

フラグがない場合、エンジンは `skip` 集合を作り、`--native-dense-gguf` の GGUF にある native 対応・2 次元テンソル名を集合へ追加します。`--native-head-gguf` を指定していれば `output.weight` も追加します。PLE key は `--native-ple-key` による対象条件と pack 内の量子化状態に応じて例外処理され、native pack では token embedding も省略対象に加わります（`src/program/generate.cpp:3776-3795`; 対応名の判定は `src/core/native_dense.cpp:154-165, 178-192`）。

この集合は pack の arena サイズ計算とロードの両方に渡され、対象行は arena に bytes を割り当てず、データポインタを持たない参照として登録されます。その後 native dense のロードが行われるため、native 経路に任せるテンソルの canonical copy が通常構成では省略されます（`src/core/weights.cpp:93-122, 224-235, 274-300`; `src/program/generate.cpp:3896-3919`）。

`--keep-canonical` を指定すると、この省略集合を作るブロック自体を通らず `skip` は空のままです。そのため arena のサイズ計算・pack ロードにはスキップ集合が渡らず、canonical copy がロードされます。後続の native dense/head のロードは別に行われるため、同じ役割の native 重みも併存します（`src/program/generate.cpp:3776-3795, 3896-3919, 5256-5263, 5552-5564`; `src/core/weights.cpp:109-122`）。

## 適用条件と副作用

- 主な効果は `--native-dense-gguf` または `--native-head-gguf` などで native 供給するテンソルがある場合に現れます。canonical copy を必要とする対象がなければ、保持する追加 copy もありません（`src/program/generate.cpp:3776-3795`）。
- `--native` による native (IQ) pack では併用できません。`native_pack` の条件判定で `o.keep_canonical` が拒否条件となり、標準エラーに「native (IQ) pack」についての案内を出して終了コード 2 で終了します。この経路ではメッセージに `--keep-canonical` 固有の拒否理由は含まれず、ほかの要件不足と同じ案内になります（`src/program/generate.cpp:3753-3765`）。
- pack の arena は VRAM に `cudaMalloc` されます。canonical copy の追加で必要量が増え、割当失敗時は標準エラーに arena の確保失敗と空き VRAM を出して終了コード 1 となります（`src/program/generate.cpp:3852-3886`）。使用量の増分はモデル・pack・native tensor 構成で異なるため、一定値とは断定できません。ソースの help は「more VRAM」と記載しています（`src/program/generate.cpp:889`）。
- `serve` の会話キャッシュ構成 fingerprint にも `keep_canonical` が記録されます（`src/program/generate.cpp:9449-9462`）。

## 出力とエラー

通常の起動では、このフラグ単独による専用メッセージやファイル出力は確認できません。ロード後の標準エラーに、pack からロードした重みの MiB 数と「canonical tensors skipped: served natively」の件数が表示されます。フラグ指定時は対象の省略をしないため、表示される skipped 件数もその分変わります（`src/program/generate.cpp:3907-3910`）。

native dense の GGUF が読み込めないなど `served_names` の処理が失敗すると、エラーを標準エラーに出し終了コード 1 で終了します。pack の `pool_bytes` 計算や `WeightTable::load` が失敗した場合も同様に終了コード 1 です（`src/program/generate.cpp:3778-3781, 3852-3855, 3896-3900`; `src/core/native_dense.cpp:178-192`）。未知の引数は標準エラーに `unknown argument` と usage を出して終了コード 2 ですが、このフラグは現行 parser に登録されています（`src/program/generate.cpp:2780, 2787-2793`）。

## 根拠

- `src/program/generate.cpp:602, 889, 2780` — 既定値、help 表示、parser 登録。
- `src/program/generate.cpp:3753-3795` — native pack の拒否、native 供給名から `skip` を作る条件と対象。
- `src/core/native_dense.cpp:154-192` — native dense 対象テンソルの名前・形式判定。
- `src/core/weights.cpp:93-122, 224-300` — skip 時の arena サイズ計算、canonical weight のロード省略。
- `src/program/generate.cpp:3852-3919, 5256-5263, 5552-5564` — arena 確保、pack load、native dense/head load とログ。
- `src/program/generate.cpp:9449-9462` — serve 構成 fingerprint への記録。

調査は指定されたソース checkout の parser と呼び出し経路に限定しました。既存バイナリの `--help`、GPU 上の実行、VRAM 増分の実測、および各モデル固有の実際のテンソル構成は確認していません。
