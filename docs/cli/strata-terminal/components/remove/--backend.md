# `--backend`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査対象 checkout は `main`、`origin/main` と一致し、`git status --short --branch` は `## main...origin/main`（clean）でした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | 必須の文字列。parser に `choices`、型変換、既定値の明示はない（省略時 `None`） |

## 役割

共通 parser 定義の説明は「この PC の GPU を検出する代わりに engine family を選ぶ」です。remove ではこの値を engine 一覧の互換性判定と Qwen engine の「使用中」判定に使います。削除候補そのものを backend で絞り込む機能ではありません。

## 使い方

```sh
strata components remove 0.2.10 --backend cuda
```

位置引数には engine の版番号または folder 名を指定します。複数 family に同じ版番号がある場合は `--family qwen` または `--family deepseek` で対象 family を絞れます。実際に削除を行うコマンドなので、実行前に `strata components engines` で対象を確認してください。

## 値と既定値

- `--backend` は値を1つ取ります。省略時は `None` で、ハードウェア検出結果をそのまま使います。
- CLI 値が空でなければ `split_backend()` が前後空白を除き小文字化します。`hip-rdna2` の形式は `hip` family と `rdna2` variant に分けられます。それ以外の値は backend 名としてそのまま渡されます。
- parser は backend 名を `choices` で制約していません。したがって任意の文字列が parser を通ります。コード上で remove 専用の未知値エラーは確認できませんでした。

## 実行時の動作

`update_cmd.run()` は最初にハードウェアを検出し、`--backend` が truthy なら検出した backend を CLI 値で上書きして、値の出所を `requested` と記録します。この値は `Context.hardware` に渡されます。`STRATA_ENGINE_BACKEND` は検出処理側で参照されますが、CLI の `--backend` が指定された場合はその backend が後から上書きします。remove 処理は `engine_library.list_engines()` から候補を探し、`delete_engine()` へ進みます（`strata_cli/update_cmd.py:244-256,272-273,358-378,395-400`、`strata_control/updater.py:261-281`）。

backend は一覧の行を消すフィルターではありません。Qwen engine は `ec.resolve(..., backend=wanted)` で選ばれる engine を `active` として扱い、DeepSeek engine は OS/backend との適合性を `fits` に記録します（`strata_control/engine_library.py:91-123,136-162`）。削除可否は一覧行の `active` と、実行中プロセスが対象 folder を使っているかで決まります。実行中の engine は `--backend` にかかわらず削除を拒否します（`strata_control/engine_library.py:84-88,167-178,294-309`）。

このため `--backend` は削除対象の選択条件ではありませんが、Qwen engine の `active` 判定には影響します。実際の環境と異なる backend を指定すると、選択中 engine の保護判定が変わる可能性があります。削除時は通常、実機を表す backend を指定するか、backend を省略して検出に任せてください。CLI 値を設定ファイルへ保存する処理は remove 経路にありません。

## 適用条件と副作用

- `--components-dir DIR` を併用すると、一覧と削除対象の検索に使う component folder を指定できます。省略時は `engine_component.components_dir()` の per-user folder（または `STRATA_COMPONENTS_DIR`）です（`strata_cli/update_cmd.py:47-50,244`、`strata_control/engine_component.py:176-186`）。
- 選択した engine が「使用中」、または実行中 program が利用している場合は削除されません。後者は process-use check で判定されます（`strata_control/engine_library.py:84-88,167-178,308-309`）。
- 削除時は対象 folder を `.deleting-<識別子>` に rename してから削除を試み、残った `.deleting-*` directory を後続処理で掃除します。Qwen engine では対応する previous/pinned/failed state と履歴も更新します。DeepSeek engine では stale pin を解除する場合があります（`strata_control/engine_library.py:310-334,341-348`）。モデルや設定、および別 family の engine は変更しません。
- `--backend` そのものはネットワークアクセスや GPU 実行を行いません。remove の処理はローカルの一覧・状態・ファイル操作です（`strata_control/engine_library.py:180-195,294-334`）。

## 出力とエラー

成功時は通常、人間向けに削除した engine の version と空き容量を表示します。`--output json` または `--json` では成功内容を JSON で出力します。`--json` は CLI の dispatch 前に `output=json` へ正規化されます（`strata_cli/update_cmd.py:395-400`、`strata_cli/cli.py:2249-2252`）。

`--backend` の値だけを理由とする parser validation error はありません。候補不在・版番号の曖昧さ・使用中 engine の削除拒否は `UpdateError` として終了コード 2 になり、通常出力では stderr に `strata: ...`、JSON モードでは error object が出ます。rename が OS error で失敗した場合は、変更なしとして終了コード 6 です（`strata_control/engine_library.py:198-211,294-316`、`strata_cli/update_cmd.py:237-242,307-311`）。

## 根拠

- 索引と scope: `docs/cli/README.md:309-325` — `strata components remove` の階層、`--backend` の予定リンク、共通 option の案内。
- parser: `strata_cli/update_cmd.py:47-58,88-95` — `--backend` の共通定義、値を取る parser action、remove への登録。
- backend 反映と remove 経路: `strata_cli/update_cmd.py:244-256,272-273,358-400`。
- backend の分解と hardware 検出: `strata_control/engine_component.py:465-471`、`strata_control/updater.py:261-281`。
- 一覧、active 判定、削除可否、ファイル・state 更新: `strata_control/engine_library.py:84-123,136-195,294-348`。
- 共通出力 option と `--json` の正規化: `strata_cli/cli.py:508-515,2249-2252`。

調査は記載した commit のソースに限定しています。実機ごとの検出結果や、削除対象を使う外部 process の状態はソース閲覧だけでは確認していません。
