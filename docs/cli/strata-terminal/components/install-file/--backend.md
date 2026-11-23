# `strata components install-file --backend`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | エンジン backend 名。CLI parser では任意の文字列を受理し、実行時に正規化・照合する |

## 役割

手元にあるエンジン package を導入するとき、どの backend family の GPU を対象にするかを指定する。指定すると Strata はその family を基にハードウェア情報を検出し、package の backend、platform、GPU アーキテクチャ、最低 runtime/driver 条件を照合する。省略時は通常の backend 自動検出を使う。`install-file` は feed から package を取得せず、引数で指定した archive を検証して導入する。

## 使い方

```sh
# AMD 用の HIP package を選んで導入する
strata components install-file ./strata-engine.tar.gz --backend amd

# HIP の特定 variant を希望する（利用可能で適合する variant がある場合）
strata components install-file ./strata-engine.zip --backend hip-rdna2
```

## 値と既定値

- 値は必須です。parser に `choices` や型変換はなく、既定値は `None` です。値なしは argparse の usage error になります（`terminal/strata_cli/update_cmd.py:47-56,92-94`）。
- backend family は `metal`、`cuda`、`hip`、`sycl`、`cpu` です。別名 `nvidia` → `cuda`、`amd` → `hip`、`intel` / `arc` → `sycl` も受け付けます（`terminal/strata_control/targets.py:22-31`、`terminal/strata_control/engine_component.py:490-502`）。
- `hip-<variant>` 形式は family `hip` と希望 variant に分解されます。空白の前後を除去し、小文字化してから解釈します（`terminal/strata_control/engine_component.py:490-499`）。
- 他の文字列も parser 自体は受理しますが、backend family として認識されない値は実行時に `ComponentProblem` となり、その値が有効 backend 一覧にない旨を返します（`terminal/strata_control/engine_component.py:542-550`）。
- `hip-<variant>` が候補選択時に優先されるのは、適合する package にその variant がある場合です。見つからなければ適合 package 群から通常の選択が続きます（`terminal/strata_control/feed.py:757-779`）。

## 実行時の動作

`--backend` が指定されると、`requested_hardware()` が backend 名を family/variant に分け、family を `STRATA_ENGINE_BACKEND` として上書きした環境情報で対象 backend のハードウェアを検出します。variant があれば選択希望として保持し、検出結果の出所も `requested` とします（`terminal/strata_cli/update_cmd.py:283-300,316-321`）。その情報は archive 内 manifest の package と照合され、family と platform が一致し、runtime・GPU アーキテクチャ・NVIDIA driver の必要条件を満たす必要があります（`terminal/strata_control/updater.py:1675-1682`、`terminal/strata_control/feed.py:731-754`）。

指定しない場合は `updater.detect_hardware()` による通常検出です。`STRATA_ENGINE_BACKEND`、保存済み family の選択、platform、利用可能な GPU probe 等が検出に影響します（`terminal/strata_control/updater.py:316-336`、`terminal/strata_control/engine_component.py:542-591`）。

このオプションは package 選択・適合判定のためのもので、`--feed` による取得先指定とは連動しません。`install-file` 分岐は feed 処理より前に archive をインストールします（`terminal/strata_cli/update_cmd.py:341-350`）。`--components-dir` は導入先を変え、`--wait` は稼働中 engine の終了待ちに関係します（同 `:47-56,314-320,341-345`）。

## 適用条件と副作用

- 対象 backend の GPU 情報が取得できない、package の backend/platform が異なる、GPU のアーキテクチャが合わない、または runtime/driver の最低条件を満たさない場合は導入を拒否します（`terminal/strata_control/updater.py:731-754,1675-1682`）。検出できない GPU 属性は空値として扱われる箇所があり、該当条件の適合性を完全には確認できない場合があります（同 `:316-336`、`terminal/strata_control/feed.py:746-754`）。
- 同 backend の variant を指定しても、その variant が適合 package にない場合に必ず失敗する仕様ではありません。選択処理は一致 variant があれば候補を絞り、なければ適合候補から選びます（`terminal/strata_control/feed.py:773-779`）。
- 処理は archive を作業用 staging directory に展開し、信頼鍵による署名と manifest 記載の全ファイルを検証します。続いて空き容量確認、engine の test start、導入先への切替を行います。選んだ archive 自体は削除されません（`terminal/strata_control/updater.py:1638-1641,1646-1674,1683-1698,1538-1549`）。
- Engine が稼働中の場合、指定値にかかわらず `--wait` がなければ通常は変更を拒否します。対話端末では待機確認を行う経路があり、`--wait SECONDS` を指定するとその時間を上限に停止を待ちます（`terminal/strata_cli/update_cmd.py:500-515`、`terminal/strata_control/updater.py:381-401`）。

## 出力とエラー

- 通常出力は成功時に導入結果を表示し、`--output json` / `jsonl` では機械可読出力になります（`terminal/strata_cli/update_cmd.py:117-139,345-350`）。
- backend 名が無効、archive が読めない・形式が対象外、署名またはファイル検証に失敗、package がこの PC に適合しない場合は失敗します。これらは主に終了コード 5 です（`terminal/strata_cli/update_cmd.py:374-385`、`terminal/strata_control/updater.py:1630-1635,1642-1645,1652-1672,1680-1682`）。稼働中 engine が残る場合は `Busy` として終了コード 7 です（`terminal/strata_control/updater.py:72-83,381-388`）。
- テスト起動に失敗した場合は失敗 package の記録を残し、切替前の engine を維持します。切替後の再解決で新 engine が選ばれない場合は rollback して終了コード 6 になります（同 `:1545-1566,1582-1599`）。
- エラーは `--output human` では stderr に `strata: ...`、JSON系では `ok: false` と error object で出力されます（`terminal/strata_cli/update_cmd.py:307-312,374-385`）。

## 根拠

- parser 定義と共通 option scope: `terminal/strata_cli/update_cmd.py:47-56,92-99`。
- install-file 分岐と `--backend` による hardware context 作成: `terminal/strata_cli/update_cmd.py:283-300,303-321,341-350`。
- backend 名・alias・variant の正規化と family 検証: `terminal/strata_control/engine_component.py:490-502,542-550`。
- backend/platform family と対応 OS: `terminal/strata_control/targets.py:22-31`。
- backend に応じた engine package の適合判定と variant 選択: `terminal/strata_control/feed.py:731-754,757-779`。
- archive 検証、適合判定、test start と切替: `terminal/strata_control/updater.py:1630-1698,1538-1627`。
- 稼働中 engine の待機・拒否経路: `terminal/strata_cli/update_cmd.py:500-515`、`terminal/strata_control/updater.py:72-83,381-401`。
