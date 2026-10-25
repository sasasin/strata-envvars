# `--spec-follow`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--spec-follow PATH` |
| 別名 | なし |
| 値 | token ID を並べたテキストファイルのパス |

## 役割

speculative decoding のベンチマークや A/B 比較で使うオプションです。verify の argmax の代わりに指定 continuation の token ID を出力列に使い、ドラフトがその continuation と一致するかを数えることで、speculation 設定が異なる実行間を比較します（`src/program/generate.cpp:673-676, 979-981`）。

## 使い方

`strata` エンジンを実行する環境で、読み込み可能な token ID ファイルを指定します。speculative loop を使うには `--spec` も指定します。

```sh
strata --pack model.gguf --tokens 1,2,3 --spec 4 --spec-follow continuation.ids
```

`--spec` の既定値は通常 build では `0` であり、Metal build では `2` です。`--spec` が有効でなく speculative loop に入らない場合、`--spec-follow` のファイルは読み込まれません（`src/program/generate.cpp:650-657, 16091-16104`）。help の説明ではベンチマーク用途で `--spec` と併用し、`--serve` では使わないものとされています（`src/program/generate.cpp:979-981`）。

## 値と既定値

- `PATH` は、整数 token ID を空白またはカンマで区切ったテキストファイルです。ファイル全体を読み込み、各 ID は `[0, 2147483647]` の整数でなければなりません（`src/program/generate.cpp:1097-1115, 16103-16107`）。
- 空ファイル、区切りだけのファイル、負数、整数として読めない値、範囲外の値は無効です。ファイルを開けない場合も読み込み失敗になります（同 `:1097-1115, 16103-16107`）。
- token ID が読み込み対象モデルの語彙範囲内かどうかは、この列 parser では検証されません（同 `:1097-1115`）。
- 既定値は空パスで、未指定時は follow 列を使いません（同 `:676, 16114-16120`）。同じオプションを複数回指定した場合は parser が同じ文字列メンバーへ順に代入するため、最後の値が残ります（同 `:2619-2622`）。
- parser は値の存在だけを確認します。値を省略すると `--spec-follow needs a value` を stderr に出して終了コード `2` で終了します（同 `:2418-2421, 2621`）。

## 実行時の動作

1. speculative loop に入ったときに `PATH` を読み、token ID 列へ変換します。開けないファイルまたは不正な列では `strata generate: cannot read --spec-follow PATH` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:16102-16117`）。
2. follow 列がある場合、生成上限 `max_new` は `min(--max-new, 列の長さ)` になります。列が `--max-new` より長ければ上限までに切り詰め、短ければ列の長さが生成上限になります（同 `:16118-16120, 16532, 16681-16686`）。
3. verify 実行後、各出力位置で元の argmax と follow token を比較して差異を記録し、その出力 token を follow の値に置き換えます。commit された token について「argmax と異なった数 / emitted token 数」を標準出力に表示します（同 `:16628-16645, 16681-16687, 16727-16733`）。

follow 列の参照位置は、その時点ですでに生成済みの token 数 `produced.size()` です。通常経路では speculative loop の前に最初の生成 token が追加されるため、その token 自体は follow に置き換わりません。指定ファイルは生成 continuation の先頭からの列として用意し、loop 開始前に生成済みの token 数に対応する先頭部分は loop では参照されない点に注意してください（`src/program/generate.cpp:16076-16092, 16639-16644`）。

## 適用条件と副作用

- 効果があるのは speculative loop に到達した実行です。`--spec` が無効、すでに `--max-new` に達した、または EOS で終了済みなど、loop が開始しない場合は `spec_follow` の読み込み処理に到達しません（`src/program/generate.cpp:16091-16104`; loop 条件の定義は `include/strata/spec/spec_start.hpp:14-18`）。
- `--serve` はソース内 help の適用対象外です。確認した通常生成経路では follow ファイルを読み込み、loop 内の出力 token を差し替えます（`src/program/generate.cpp:979-981, 16102-16120, 16639-16645`）。
- このオプションはファイルを読むだけで、指定ファイルへの書き込みはありません。生成結果とは別に、follow 列と argmax の差異数を stdout に出します（同 `:16103-16107, 16731-16733`）。
- parser 上の値検査はありません。ファイル読み込みと token ID 検証は speculative loop 到達時に行われます。通常 decode のみの実行では不正なパスや内容でも検出されません（同 `:2619-2622, 16102-16117`）。

## 出力とエラー

- 引数値の欠落: `--spec-follow needs a value`、stderr、終了コード `2`（`src/program/generate.cpp:2418-2421`）。
- loop 到達時のファイル読み込み失敗または token 列の不正: `strata generate: cannot read --spec-follow PATH`、stderr、終了コード `2`（同 `:16114-16117`）。
- 正常終了時、follow 列が有効なら `follow` 行に argmax と異なった emitted token 数と、比較対象の emitted token 数を stdout に表示します（同 `:16731-16733`）。

## 根拠

- option の値保存、既定値、help: `src/program/generate.cpp:673-676, 979-981, 2621`。
- 共通 token 列 parser の区切り・範囲・空列判定: `src/program/generate.cpp:1097-1115`。
- speculative loop でのファイル読み込み、失敗経路、生成上限: `src/program/generate.cpp:16102-16124`。
- loop 開始条件: `include/strata/spec/spec_start.hpp:14-18`。
- follow による argmax 置換・差異集計・表示: `src/program/generate.cpp:16628-16645, 16681-16687, 16727-16733`。
- 同じ option と処理を持つ SYCL 側 parser/help/loop も確認しました: `sycl/src/program/generate.cpp:634-637, 880-882, 1919, 12389-12410, 12751-12752, 12799, 12837`。この文書の主対象スコープは索引が指定する `src/program/generate.cpp` です。

調査は上記 checkout のソースと索引・配置規約に限定しました。同一 revision の既存 CLI バイナリや Release 配布物は照合していません。
