# `--draft-costs-key`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--draft-costs-key` |
| 別名 | なし |
| 値 | 必須の文字列（追加の識別情報） |

## 役割

`--draft-costs` が使うドラフト窓コスト表の識別キーに、呼び出し元が指定する文字列を追加する。モデルやエンジン設定などから作られる基本キーに追加される値であり、コスト表の有効範囲を呼び出し元側の識別情報でも分けたい場合に使う。単独では表の読込・学習を有効にせず、その処理は `--draft-costs` が空でなく、ドラフトポリシーがすでに固定されていない場合に限って実行される。

## 使い方

```sh
# サーバーでコスト表を使い、表のキーにエンジン識別情報を追加する
strata --serve --native ./model.gguf --draft-costs ./draft.costs --draft-costs-key 'engine file 123456 bytes'
```

## 値と既定値

- 値は必須です。parser は次の argv 要素を文字列として保存し、数値・形式・空文字列の検証はしません。値を省略すると stderr に `--draft-costs-key needs a value` を出して終了コード `2` で終了します（`engine/src/program/generate.cpp:3837-3842,4208-4209`）。
- 既定値は空文字列です。指定を複数回行った場合、引数を順に処理するため最後の値が保存されます（`engine/src/program/generate.cpp:3837-3842,4208-4209`）。
- この値に改行または復帰文字が含まれる場合、コスト表ファイルに書く際は空白に置換されます（`engine/src/spec/draft_policy.cpp:256-260,381-382`）。

## 実行時の動作

コスト表処理が有効なとき、エンジンはバージョン、backend、検出した GPU の情報、driver/runtime、適応制御や cost-aware window の設定、および `--draft-costs` 関連フラグを除いたエンジン引数から基本キーを構成します。ファイル引数は basename とサイズ、ディレクトリ引数は basename、その他の引数は値を含めます。その末尾に本オプションの値を `|server ` に続けて加えます（`engine/src/program/generate.cpp:2286-2290,2291-2334`）。

コスト表の読込時は、ファイルの `key` 行と生成キーが一致することを要求します。不一致の表は読込失敗として扱われ、既存表をそのまま使わず、通常リクエストの実測値による作成・再学習経路に進みます（`engine/src/spec/draft_policy.cpp:263-270`; `engine/src/program/generate.cpp:16343-16368`）。したがって値を変えると別キーとなり、指定した `--draft-costs` ファイルが別用途として認識されることがあります。

## 適用条件と副作用

- 本オプションがキーに反映されるのは、`--draft-costs` の値が空でなく、ドラフトポリシーが固定済みでない場合です。それ以外では値を保存してもコスト表処理で参照されません（`engine/src/program/generate.cpp:16343-16345`）。
- `strata serve` のサーバーは、設定に応じてこの値を自動付与します。実行エンジンのファイルサイズが取得できた場合、`engine file <サイズ> bytes` を追加キーとして渡します（`terminal/serve/server.py:3656-3679`）。
- キーの不一致・表の欠落や破損はコスト表の再作成につながります。学習または校正結果は `--draft-costs` が指定したパスへ書き込まれ、既存ファイルは一時ファイル経由で置き換えられます。書込失敗時は理由を stderr の状態メッセージに含め、次回起動時に再学習となる旨を出します（`engine/src/spec/draft_policy.cpp:370-429`; `engine/src/program/generate.cpp:16360-16403,23134-23189,23192-23212`）。

## 出力とエラー

- 本オプション固有の形式検証や警告はありません。値がない場合は前述の stderr と終了コード `2`、未知の引数は `unknown argument` と usage を stderr に出して終了コード `2` です（`engine/src/program/generate.cpp:3839-3841,4263-4268`）。
- 値が既存表のキーと合わない場合、表読込の理由（`learned on another machine or with other settings`）がサーバーの stderr 状態メッセージに現れ、要求処理を継続して実測・学習経路に移ります（`engine/src/spec/draft_policy.cpp:269-270`; `engine/src/program/generate.cpp:16360-16403`）。

## 根拠

- `engine/src/program/generate.cpp:936-941` — 関連 option と `Options` の既定値。
- `engine/src/program/generate.cpp:3837-3842,4208-4209` — 値取得、欠落時のエラー、option 登録。
- `engine/src/program/generate.cpp:2286-2334,16343-16403` — キー構成、適用条件、表読込とキー不一致時の経路。
- `engine/src/spec/draft_policy.cpp:263-270,370-429` — キー照合、表ファイルの書込と置換。
- `engine/src/program/generate.cpp:23134-23212` — 学習・校正後の保存と失敗メッセージ。
- `terminal/serve/server.py:3656-3679` — Terminal サーバーがエンジン識別情報を値として渡す条件。
