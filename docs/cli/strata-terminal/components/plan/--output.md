# `strata components plan --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components plan` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

コンポーネント manifest を現在の platform と任意指定の backend に照らして調べる `strata components plan` の出力形式を選びます。`--output` は表示形式だけを変え、manifest の読み込みや互換性判定の条件は変えません。結果は標準出力へ出され、出力ファイルは作成しません。

## 使い方

```sh
strata components plan ./component-manifest.json --output json
```

`manifest` は必須の位置引数です。`--output` は `strata components plan` 固有であり、他の `components` サブコマンドへは適用されません。

## 値と既定値

- `human` は既定値です。コンポーネント ID・version・kind、対応 platform、判定対象、artifact の合計サイズ、cache key の先頭、利用可否、理由、依存 component を読みやすい複数行で表示します。
- `json` は schema version 1 の JSON オブジェクトを一行で標準出力へ出します。成功時の `ok`、component の識別情報、backend・target・platforms、cache key、`usable` と `reasons`、artifact 情報、合計 bytes、requires、entrypoint を含みます。
- それ以外の値（空文字を含む）は parser の choices により拒否されます。`argparse` の usage/error を表示して終了コード 2 となります。
- `--json` という alias はこの parser には定義されていません。

## 実行時の動作

両形式とも同じ処理で manifest を読み、`components.check_compatible` の結果を表示します。`--target` が指定されていない場合は host platform が対象になり、`--backend` は指定時のみ判定に渡されます。これらの値によって互換性の判定結果は変わりますが、`--output` によっては変わりません。

JSON 成功出力は `_success(..., machine=True)` を通り、`{"schema_version":1,"ok":true,...}` の形です。互換性がない場合もコマンドの終了コードは 0 で、JSON ではトップレベルの `ok` は `true`、判定結果の `usable` が `false` となり、理由は `reasons` に入ります。human 出力では `usable NO` と理由を表示します。

## 適用条件と副作用

このオプションは、manifest の読み込み・互換性確認をする `plan` サブコマンドにのみ適用されます。処理は読み取り専用で、ソースの説明と実装は「何もダウンロード、展開、変更しない」と明示しています。`--output` 自体によるファイル・ネットワーク・プロセス変更はありません。

## 出力とエラー

- manifest のパスが存在しない場合は終了コード 2 です。`human` では `strata: ...` を標準エラーへ、`json` では `{"schema_version":1,"ok":false,"error":{"code":2,"message":"..."}}` を標準出力へ出します。
- manifest が不正な JSON、schema 不一致、必須値不足など `ComponentError` となる場合は、その例外の code で失敗します。`ComponentError` の既定 code は 6 です。エラーの出力先・形式は上記と同じく `--output` に応じます。
- パスの読み込みで `OSError` が起きた場合は共通例外処理で終了コード 6 となり、`json` では JSON error、`human` では標準エラーになります。
- parser が受け付ける値以外を指定した場合、コマンド本体に入る前に argparse が失敗します。

## 根拠

- `strata_cli/cli.py:114-128` — `components plan` parser と `--output` の選択肢・既定値。
- `strata_cli/cli.py:1966-2011` — manifest の読込、platform/backend 判定、human/JSON 成功出力、読み取り専用の説明。
- `strata_cli/cli.py:527-542` — machine error / success の JSON 形式と human error の標準エラー出力。
- `strata_cli/cli.py:2129-2130,2217-2237` — `components plan` から処理への dispatch と parser 後の実行。
- `strata_control/components.py:136-160,165-205` — manifest の JSON・schema・内容 validation。
- `strata_control/targets.py:12-18` — `ComponentError` の code 既定値。
