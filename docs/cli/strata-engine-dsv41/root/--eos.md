# `--eos`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 engine） |
| オプション | `--eos` |
| 別名 | なし |
| 値 | EOS token ID。カンマまたは半角空白区切りの整数列を指定する実装。 |

## 役割

EOS token ID を指定します。`--serve` の生成停止判定と、`--score` の EOS 除外確率計算に使われます。初期値は `1` です。単発の `--ids` 実行、画像 encode、profile run、spec eval では、この値を参照する処理はありません。

## 使い方

```sh
strata-dsv41 --pack PACK --serve --eos 1,2
strata-dsv41 --pack PACK --score IDS.json --score-out RESULT.tsv --eos 1
```

`PACK` は DSV41 model pack、score の `IDS.json` は score 用 segment 定義です。`--eos` はその後ろの引数を値として1つ消費します。

## 値と既定値

- 省略時は文字列 `"1"`。serve はこれを ID `1` のリストとして解釈し、score は整数 `1` として扱います。
- 指定値は `strtol` による10進数変換で読み取られ、serve の複数値はカンマまたは半角空白で区切れます。先頭から数値に変換できない箇所で読み取りを止めます。空値や数値を含まない文字列を明示しても専用の validation error はなく、serve では空リスト、score では `atoi` により `0` になります。
- ID の範囲確認は parser では行われません。score では `0 <= ID < vocab` の場合だけ EOS log probability を計算します。serve は ID を生成 token と比較します。
- 同じオプションを複数回指定すると、最後に parser が読んだ文字列が残ります。

## 実行時の動作

`--serve` では生成した token を `T <id>` として出力してから EOS リストと比較します。一致すれば生成を終了し、完了行の finish reason を `stop` にします。そのため EOS token 自体も `T` 行に含まれます。EOS が空リストまたは不一致なら、要求 token 数や model context 上限など別の終了条件まで続きます。

`--score` では指定 EOS の log probability を score TSV に記録し、対象が EOS でない token の `lt_ne` は EOS を分布から除外した確率として算出します。`--eos` は score 対象列を途中で止める指定ではありません。出力先は `--score-out`、省略時は入力 IDS パスに `.tsv` を付けた名前です。また同名の `.seg.json` も作成されます。

このオプションは `--serve` または `--score` の経路でのみ参照されます。parser 上は他の動作モードとの併用を拒否しませんが、単発生成・profile run・spec eval・画像 encode には効果がありません。

## 適用条件と副作用

`strata-dsv41` は `STRATA_BUILD_DSV41=ON` で作られる独立 executable です（既定では build されません）。`--serve` と `--score` はモデルをロードした後に選択されるため、このオプション自体がファイルやネットワークを操作することはありません。score 実行は `--score-out` と `.seg.json` をバイナリ書き込みモードで開くため、同名ファイルがあれば上書きします。

## 出力とエラー

- `--eos` の値が欠けると stderr に `--eos needs a value` を出して終了コード `2` になります。
- `--eos` 自体に対する不正値・範囲エラーは実装されていません。整数列に解釈できなければ前述の空リストまたは `0` の扱いになります。
- serve の通常終了時は EOS 終了を `DONE` 行の `stop` として出力します。
- score の出力ファイルを開けない場合は stderr に `strata-dsv41: cannot write <path>` を出して終了コード `1` になります。

## 根拠

- parser の初期値、値取得、score/serve への引き渡し: `src/dsv41/ds4_main.cpp:1187-1197`, `src/dsv41/ds4_main.cpp:1200-1208`, `src/dsv41/ds4_main.cpp:1222`, `src/dsv41/ds4_main.cpp:1275-1301`
- ID リストの変換規則: `src/dsv41/ds4_main.cpp:71-83`
- serve の EOS 判定・token 出力・終了理由: `src/dsv41/ds4_main.cpp:881-891`, `src/dsv41/ds4_main.cpp:913-919`
- score の EOS 確率処理とファイル出力: `src/dsv41/ds4_main.cpp:1006-1028`, `src/dsv41/ds4_main.cpp:1067-1075`
- DSV41 executable の build 条件: `CMakeLists.txt:797-811`
- 利用者向け score 例: `docs/DEEPSEEK41.md:130-138`

## 調査上の制約

索引は `--eos` 文書を予定リンクとして掲載していますが、同 revision の `usage()` に出るオプション一覧には `--eos` の記載がありません（`src/dsv41/ds4_main.cpp:85-94`）。parser で受理され、上記の使用箇所を確認したため本書はソース実装に基づいています。調査 checkout で既存の同 revision executable が確認できることを前提とした help 実行は行っていません。
