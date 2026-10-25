# `strata components engine`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engine` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/engine_component.py` |
| 用途 | ローカルにある engine component の一覧と、この PC で起動可能な engine の判定 |

## 役割

コンポーネントフォルダー内の engine manifest を読み、OS・GPU backend・engine の適合性とファイル整合性を確認します。利用可能な engine があれば選ばれた実行ファイルと version を表示し、なければ不適合の理由を報告します。このコマンド自体は engine のダウンロードやインストールをしません（parser と status 処理: `strata_cli/cli.py:132-138,2014-2041`; `strata_control/engine_component.py:1-6,969-988`）。

これは Terminal CLI の component 状態確認コマンドです。ネイティブ推論 engine の引数 parser とは別の CLI です。

## 使い方

```sh
# 既定のコンポーネントフォルダーと自動検出 backend で確認
strata components engine

# backend を指定し、全ファイルをハッシュ検証して JSON で出力
strata components engine --backend cuda --full --output json

# 調べるコンポーネントフォルダーを指定
strata components engine --components-dir /path/to/components
```

## 実行モードと主要な動作

- `--output human`（既定）はコンポーネントフォルダー、この PC の platform/backend と検出元、検出した package、問題のある package、使用可能なら選択 engine の実行ファイルと version を表示します。利用可能な engine がない場合は notice を標準エラーに出します。最後に「何もダウンロード・変更していない」旨を表示します（`strata_cli/cli.py:2023-2041`）。
- `--output json` は `schema_version: 1`、`ok` と status report を JSON として標準出力へ出します（`strata_cli/cli.py:2023-2026`）。選択 engine のほか、一覧、problem、pinned/previous 状態、update notice、`acquires: false` を含みます（`strata_control/engine_component.py:977-981`）。
- backend は `--backend` があればそれを使い、省略時は `STRATA_ENGINE_BACKEND`、platform/adapter 情報、既存 GPU probe tool などから判定します。自動判定できない場合は CPU を選択します（`strata_control/engine_component.py:439-482,869-875`）。
- package は platform/backend の適合性に加えて、記録された最低 runtime、GPU architecture、NVIDIA driver の条件を確認して候補を絞り、usable な候補から pinned package があればそれを優先し、なければ version 等で選びます（`strata_control/engine_component.py:881-918,937-944`）。
- 通常は manifest に列挙された各ファイルの存在・通常ファイル性・サイズを調べ、entrypoint の SHA-256 を検証します。`--full` を付けると列挙された全ファイルの SHA-256 も検証します（`strata_control/engine_component.py:402-427`）。
- 実行前に CLI 共通処理が呼ばれます。Windows で昇格実行されている場合は、そのプロセスが以後作るファイルの既定 owner/DACL をユーザー向けに設定しようとします。これは engine 状態確認固有の処理ではなく、`adopt_user_defaults()` は Windows 以外では何もしません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-385`）。

## 主なオプション

このコマンドに固有のオプションは次のとおりです。値の受理と詳細は個別文書を参照してください。

- [`--backend`](--backend.md) — engine family の指定。省略時は自動判定。
- [`--components-dir`](--components-dir.md) — component root の指定。省略時は環境変数またはユーザー領域を使います。
- [`--full`](--full.md) — manifest にある全ファイルの SHA-256 を検証。
- [`--output`](--output.md) — `human` または `json` の出力形式。
- [`--help`](--help.md)（alias: `-h`）— このコマンドのヘルプ。

オプション文書の索引は [`docs/cli/README.md`](../../../README.md) を参照してください。

## 注意点と失敗経路

- 使用可能な engine が見つからない場合、report を表示して終了コード `5` を返します。human 形式では notice を stderr に、JSON 形式では `ok: false` を含む report を stdout に出します（`strata_cli/cli.py:2020-2041`）。
- `--backend` は parser で候補値を制限していません。指定 backend に合う package がなければ通常は usable なしとして終了コード `5` になります。省略時の `STRATA_ENGINE_BACKEND` が不正なら backend 判定の `ComponentProblem` を CLI がエラーとして処理し、終了コード `2` になります（parser: `strata_cli/cli.py:134`; detector: `strata_control/engine_component.py:443-447`; status: `strata_control/engine_component.py:973-987`; dispatcher: `strata_cli/cli.py:2019-2022,2166-2173`）。
- manifest の読み取り問題やファイル検証問題は package ごとの `problems` / notice に含めて報告されます。全ての適合 package が整合性検査に失敗するケースも、この status コマンドでは usable なしの report として扱います（`strata_control/engine_component.py:780-793,911-936,982-988`）。
- backend 自動判定は読み取り中心ですが、既にインストールされている `nvidia-smi`、`rocminfo`、`hipInfo`、`sycl-ls` 等を最長8秒の timeout 付きで問い合わせる場合があります（`strata_control/engine_component.py:439-482`）。`--full` は全ファイルを読み込んでハッシュ化するため、package のファイル数・サイズに応じて確認時間が増えます（`strata_control/engine_component.py:378-399,402-425`）。
- inventory の scan は隠し directory を除き、最大64 package directory を処理します。engine root を読み取れない場合は scan 結果を空として扱い、その結果 engine 不在の report になることがあります（`strata_control/engine_component.py:780-793`）。

## 根拠

- `strata_cli/cli.py:114-138` — `components engine` の command 階層と parser 定義。
- `strata_cli/cli.py:2014-2041,2166-2173` — status 呼び出し、出力、終了コードと例外の CLI 表示。
- `strata_cli/cli.py:2217-2224` — 共通起動処理。
- `strata_control/engine_component.py:176-190,780-793` — component root の決定と inventory scan。
- `strata_control/engine_component.py:402-427,439-482,859-944,969-988` — 検証、backend 判定、engine 選択、status report。
- `strata_control/private_files.py:349-385` — Windows 昇格プロセスの既定 owner/DACL 設定。
