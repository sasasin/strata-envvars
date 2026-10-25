# `--short-read`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの root 引数 parser） |
| オプション | `--short-read N` |
| 別名 | なし |
| 値 | 0 以上の整数として扱うトークン数 |

## 役割

`--serve` のプロンプト読み込みで、短いテキスト区間を通常の batched prompt path ではなく decode の verify windows 経由で読む上限を指定します。説明文と実装コメントは、短いチャットメッセージや assistant header などにこの経路を使う設定として示しています。`strata --help` の表示内容も `src/program/generate.cpp` の usage 定義（931–932行）にあります。

## 使い方

```sh
strata --serve --short-read 64 --native /path/to/model.gguf
```

これはネイティブエンジンのオプション例です。`--short-read` は `--serve` なしでも parser に受理されますが、実際のプロンプト振り分けは serve のリクエスト処理にあります。

## 値と既定値

- 省略時は `64`。
- parser は `std::atoll` で値を読み、`std::max(0LL, ...)` で負値を `0` に丸めます。`0` は短い区間も verify windows に回さず、batched prompt path を使う設定です。
- 正の上限値はコード上で別途制限されていません。値は `int64_t` に保持されます。
- 数値変換は `atoll` に委ねられ、先頭に整数がない値は 0 と同様に扱われます（整数の後ろに文字が続く値は整数部分まで読み取られます）。重複指定を拒否する処理はなく、引数走査で後に現れた値が残ります。
- 値を省略すると parser の `next()` が `--short-read needs a value` を stderr に出し、終了コード 2 で終了します。

## 実行時の動作

serve の各リクエストでは `req_short_read` を設定値で初期化し、各プロンプト区間 `[a,b)` の長さ `b-a` がこの上限以下なら windows 経路の候補になります。区間が上限を超える場合は batched 経路を使います。候補区間は `read_windows`（通常は verify windows、条件を満たす pipeline 設定では pipelined windows）へ渡され、そうでない区間は `read_part` へ渡されます。区間ごとに判定するため、長いプロンプトの一部は batched、短い末尾の一部は windows という組み合わせもあります。

- `STRATA_CKPT_REREAD` が設定されていると短区間判定を無効化し、すべて batched path にします。
- 画像埋め込み行を含む区間は windows 対象になりません。
- `STRATA_PIPELINE_SWITCH` が設定され、pipeline 実行中にそのファイルを開けた場合、ファイル内の `short_read=N` がリクエスト単位の上書き値になります。値は同様に 0 以上へ丸められ、選ばれた値が stderr に表示されます。これは診断用の環境変数経路です。
- `--short-read` が正のとき prompt windows で non-finite logits が検出された場合、次のリクエストは一度だけ `req_short_read=0` にして全プロンプトを batched path で読みます。その際 stderr に理由が出ます。
- `--prefill-head-alias` は `--short-read 0` を必要条件とし、正の値なら利用不可として終了コード 2 になります。
- `--prompt-cache-tail` の追加 checkpoint 判定でも `o.short_read` が閾値として参照されます（環境変数によるリクエスト単位の上書き値ではありません）。

## 適用条件と副作用

この設定が読み込み経路を変えるのは `--serve` のプロンプト処理です。値の指定自体にモデル・backend の追加 validation はありません。`--pipeline-windows` の有効化は必須ではなく、verify windows 経路は通常実行されます。適用時は prompt の計算経路が変わり、通常 path では区間を batched に読み、短い対象区間ではトークンを verify windows に通します。ファイルの作成・変更やネットワーク接続などの副作用は、このオプションの実装箇所にはありません。

## 出力とエラー

有効な値に対する専用の通常出力や警告は確認できません。パラメーター欠落時は stderr に値不足を出して終了コード 2、未知の引数は stderr に `unknown argument` と usage を出して終了コード 2 です。windows 経路で読み込みに失敗した場合は serve の一般エラー経路で stderr と `ERR ...` を出し、通常は終了コード 1 で返ります。non-finite prompt window の検出時はエラー詳細を stderr に出し、該当リクエストは `DONE nonfinite` で終了します。

## 根拠

- 索引上の配置と scope: `docs/cli/README.md:12`、`docs/cli/README.md:1128-1135`、対象リンク `docs/cli/README.md:1282`。
- 値の既定値: `src/program/generate.cpp:762-765`。
- help 表示: `src/program/generate.cpp:931-932`。
- parser の値変換と既定値上書き: `src/program/generate.cpp:2416-2421`、`src/program/generate.cpp:2669`。
- 上限判定、環境変数による無効化、画像区間除外、診断用上書き: `src/program/generate.cpp:13057-13103`。
- windows/batched 経路の選択と呼び出し: `src/program/generate.cpp:14065-14091`。verify windows 処理は `src/program/generate.cpp:13194-13253`。
- non-finite 後の一回限りの無効化: `src/program/generate.cpp:9355-9360`、`src/program/generate.cpp:9653-9666`、`src/program/generate.cpp:12549-12557`、`src/program/generate.cpp:13065-13070`。
- `--prefill-head-alias` との条件: `src/program/generate.cpp:5576-5588`。
- prompt-cache tail 判定: `src/program/generate.cpp:9907-9912`。
- parser の unknown argument と usage 経路: `src/program/generate.cpp:2787-2793`。
- serve の区間エラー出力: `src/program/generate.cpp:14107-14118`。

調査対象 checkout は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、branch `main` で、調査時点の `git status --short --branch` は `## main...origin/main` でした。作業ツリー変更は確認されませんでした。既存の build 済み CLI の revision を確認できないため、実行による `--help` 照合は行わず、同 revision のソース内 usage と parser を照合しました。
