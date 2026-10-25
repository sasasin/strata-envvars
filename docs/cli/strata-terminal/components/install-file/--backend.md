# `--backend`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | バックエンド名を1つ取る。parser に `choices` や型変換の指定はない |

## 役割

ローカルから導入するエンジン package について、この PC が必要とする backend family を指定します。package の backend と指定値が一致しない場合、適合しない package として拒否されます。省略すると PC の検出結果を使います。

## 使い方

```sh
strata components install-file ./strata-engine.tar.gz --backend cuda
```

位置引数 `file` は手元にあるエンジン package のパスです。`--backend` は `--feed` のように package の取得先を指定するものではありません。

## 値と既定値

- 既定値は `None` で、省略時は `updater.detect_hardware()` が得た backend を使います。
- parser は値を文字列のまま受け取り、許容値を parser 層では制限しません。同じオプションを複数指定した場合は通常の `argparse` の `store` 動作により最後の値になります。
- package manifest の backend は `metal`、`cuda`、`hip`、`sycl`、`cpu` のいずれかに制限されています。指定値はその backend と大文字小文字を含めて一致する必要があります。未知の値や異なる表記は parser エラーではなく、後段の適合判定で拒否されます。
- 空文字列を値に渡すと `if a.backend` が偽になるため、明示値として使われず自動検出の値が残ります。

## 実行時の動作

`install-file` は `_common()` が共通オプションを登録し、`--backend` 自体の指定は `default=None` です。実行時には最初にハードウェア情報を検出し、値が truthy なら `hardware["backend"]` をその値に、`backend_source` を `requested` に置き換えます。そのハードウェア情報を用いて `install_engine_file()` を呼び出します。

package の署名・ファイル検証後、manifest から読んだ backend と PC 用に選んだ backend が一致するかを含めて package の適合性を確認します。OS/platform、Control runtime の最低バージョン、検出済み GPU の CUDA architecture / NVIDIA driver、HIP architecture も適合判定の対象です。成功後は staged engine の test start を行い、問題がなければ engine を切り替え、以前の engine を保持します。

環境変数 `STRATA_ENGINE_BACKEND` は `detect_hardware()` 内で先に評価されます。`--backend` を指定すると backend と source は `requested` に上書きされますが、検出時に得た runtime、driver、GPU architecture 等の情報は再検出されません。したがって指定 backend と実機の組合せをソースが再調査するわけではなく、最終的な test start で起動できない package は失敗し得ます。`STRATA_ENGINE_BACKEND` 自体が無効な値なら、CLI 値による上書きより前の検出段階でエラーになります。

## 適用条件と副作用

- backend family は対象 OS/platform と組み合わせて適合判定されます。対応表は `metal` が macOS arm64、`cuda` / `hip` が Windows x86_64 と Linux x86_64、`sycl` が Linux x86_64、`cpu` が macOS arm64/x86_64、Windows x86_64、Linux x86_64 です。
- package file の読み取り、staging directory への展開、署名と全ファイルの検証、engine の test start、および成功時の component folder 内の切替・状態履歴更新を伴います。ダウンロードは行わず、指定した元 archive は削除しません。
- serving 中の engine がある場合、`--wait` なしでは対話端末で待機確認を行い、machine output または非対話時は待たずに busy error になります。待機時間も `--wait` で指定できます。

## 出力とエラー

- 成功時は既定の human output に結果を表示し、`--output json` または `jsonl` では JSON を出力します。JSONL の進捗イベントは helper が出力しますが、install-file の通常経路は feed download をしないため download 進捗はありません。
- package の不在・形式不正、manifest / 署名 / ファイル検証失敗、指定 backend や platform などとの不適合は `UpdateError` として拒否コード 5 になります。空き容量不足・test start 後の切替失敗などはコード 6、engine busy はコード 7 です。`update_cmd.run()` は human mode では `strata: ...` を stderr に、machine mode では `ok: false` の JSON error を stdout に出します。
- 検証・適合判定に失敗した場合、staging directory は後処理で削除されます。切替後に resolver が新しい engine を選ばない場合は新規配置を `.rejected` に移し、以前の engine を維持します。

## 根拠

- parser と共通 option: `strata_cli/update_cmd.py:30-61`。コマンド dispatch: `strata_cli/cli.py:139-140,2135-2137`。
- hardware 検出結果への適用、install 呼び出し、出力・例外処理: `strata_cli/update_cmd.py:174-216,246-255`。
- backend 環境変数の検証と検出: `strata_control/updater.py:255-276`、`strata_control/engine_component.py:439-447`。
- backend の一致、platform/runtime/GPU 条件: `strata_control/feed.py:372-395`。対応 backend/platform: `strata_control/targets.py:20-29`。manifest backend の制約: `strata_control/engine_component.py:267-286`。
- ローカル package の展開・署名/内容検証・適合確認・元 archive を残す処理: `strata_control/updater.py:1088-1148`。
- test start、切替、前版保持と rollback 可能な状態の更新: `strata_control/updater.py:994-1077`。
- 空き容量不足コード: `strata_control/updater.py:454-473`。serving 時の待機・拒否と終了コード: `strata_control/updater.py:306-317`、`strata_cli/update_cmd.py:258-273`。

調査対象は上記 commit の checkout です。CLI `--help`、Release archive、および異なる OS/backend 実機での実行は調査していません。動作の説明は同一 revision の parser と実装ソースに基づきます。
