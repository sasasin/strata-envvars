# `--target`

- ツール: `strata-terminal`
- コマンド: `strata components plan`
- 調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）

## 用途

コンポーネント manifest の利用可否を判定する対象 platform key を指定します。別のマシン向け manifest を現在の環境から確認する用途です。manifest は位置引数で渡します。

```sh
strata components plan ./component-manifest.json --target linux-x86_64
```

## 値と既定値

`--target` は値を1つ取ります。parser は型変換や `choices` 検証を行わず、既定値は `None` です。省略時は `components.host_platform()` が現在の OS と CPU アーキテクチャから platform key を作ります（例: `linux-x86_64`）。明示値は文字列のまま判定関数に渡されます。

空文字列は parser 上受理され、実行時の `a.target or ...` により未指定と同じく現在の platform key に置き換わります。その他の値にも形式検証・正規化・大文字小文字の補正はありません。manifest の `platforms` に同じ文字列があるか、および backend の対応表に含まれるかで判定されます。

## 実行時の動作

`strata components plan` は manifest を UTF-8 で読み込み、厳密に解析した後、`--target` の値を `check_compatible` に渡します。対象値は manifest の platform 一覧との照合に使われ、manifest に backend があれば backend と `--backend` の一致、および対象 platform での backend 対応状況も判定されます。`--target` は `--backend` の値を変更せず、両者は独立した照合条件です。

結果には選択された `target`、manifest の `platforms`、`usable`（理由が空なら true）と `reasons` が含まれます。既定の human 出力は target と可否を表示し、`--output json` では同じ判定結果を JSON で返します。このコマンドは manifest を読むだけで、ダウンロード、展開、状態変更はしません。

## 適用条件と副作用

`--target` を指定すると、ホストの OS/CPU から作る target の代わりにその文字列を使います。別 platform の互換性を照会できますが、その platform 上で実行したり、実機の状態を検証したりするものではありません。platform key の有効性は manifest との完全一致と backend 対応表で評価されます。

値を省略した場合、OS 名が `macos` / `linux` / `windows` のいずれにも対応せず host key を作れないと `ComponentError` が発生します。この例外は `_components_plan` 内で捕捉されず、現在の `_run` の捕捉対象にも含まれないため、通常の `strata:` エラー整形や終了コードはソースから確認できません。明示的な `--target` があれば host key 生成を通りません。コマンドの処理は manifest 読み込みと判定に限られます。

## 出力とエラー

- manifest ファイルが存在しない場合は stderr に `strata: no component manifest at ...` を出し、終了コード 2 です。
- 不正 JSON、必須項目不足、platforms の欠落・空リストなど manifest の解析エラーはエラーとして出力されます。`ComponentError` の既定終了コードは 6 です。
- manifest が読めていても target や backend が非互換なら、`usable: false` と理由を表示します。この非互換レポート自体は正常な判定結果として終了コード 0 です。
- human 出力は標準出力、`--output json` の成功結果も標準出力です。JSON の成功結果には `schema_version: 1` と `ok: true` が付きます。

## 根拠

- parser と既定値・help: `strata_cli/cli.py:120-128`
- manifest の読み込み、target の選択、判定、結果と出力: `strata_cli/cli.py:1966-2011`
- target の manifest platform 照合と backend 条件: `strata_control/components.py:208-228`
- manifest の platform 必須条件と解析: `strata_control/components.py:136-205`
- host platform key の生成と backend 対応表: `strata_control/targets.py:20-51`
- JSON / human エラー出力形式: `strata_cli/cli.py:527-542`
- `components plan` から handler への dispatch: `strata_cli/cli.py:2127-2135`
